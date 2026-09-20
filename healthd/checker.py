"""探针运行器：注册探针，手动跑一轮，或起常驻线程定期自检。"""

import random
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from healthd.board import ProbeResult, StatusBoard

ProbeFn = Callable[[], str]
OnChangeFn = Callable[[str, str], None]

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_DOWN = "down"


class _RealClock:
    """真实时钟：monotonic 计时，sleep 可被 wake 提前唤醒（用于 stop）。"""

    def __init__(self):
        self._wake = threading.Event()

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        self._wake.wait(max(0.0, seconds))

    def wake(self) -> None:
        self._wake.set()


class Probe:
    """一个探针 = 名字 + 检查函数 + 可选超时秒数。

    检查函数无参调用：通过则返回细节字符串（可为空），
    失败直接抛异常。设了 timeout 时探针在独立线程里跑，
    超时未返回即判失败，不再拖死整轮检查。
    """

    def __init__(self, name: str, fn: ProbeFn, timeout: Optional[float] = None):
        self.name = name
        self.fn = fn
        self.timeout = timeout


class CheckRunner:
    """按注册顺序串行跑一轮探针，结果写进状态板。

    可手动 run_once，也可 start() 起常驻线程每 period 秒跑一轮
    （周期在 [period-jitter, period+jitter] 间抖动，时钟可注入）。
    k 为就绪门限：通过数 >= k 即可接流量（ready），
    全部通过状态为 ok，达到 k 但不全为 degraded，低于 k 为 down。
    """

    def __init__(self, board: Optional[StatusBoard] = None, k: int = 1):
        if k < 1:
            raise ValueError("k must be >= 1")
        self.board = board if board is not None else StatusBoard()
        self.k = k
        self._probes: Dict[str, Probe] = {}
        self._order: List[str] = []
        self._lock = threading.RLock()
        self._on_change: List[OnChangeFn] = []
        self._clock = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def register(self, name: str, fn: ProbeFn, timeout: Optional[float] = None) -> None:
        """注册探针。同名重复注册抛 ValueError。

        timeout 为可选超时秒数：探针超时未返回判失败，
        detail 记 "timeout after ..."，不影响同轮其他探针。
        """
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive")
        with self._lock:
            if name in self._probes:
                raise ValueError(f"probe already registered: {name}")
            self._probes[name] = Probe(name, fn, timeout)
            self._order.append(name)

    def names(self) -> List[str]:
        """按注册顺序返回探针名列表副本。"""
        with self._lock:
            return list(self._order)

    def on_change(self, fn: OnChangeFn) -> None:
        """注册整体状态翻转回调 fn(old, new)，在检查线程里触发。

        回调抛错只跳过该回调，不中断检查循环。
        """
        with self._lock:
            self._on_change.append(fn)

    def run_once(self) -> Dict[str, ProbeResult]:
        """按注册顺序串行跑一轮全部探针，返回状态板快照。

        单个探针抛异常或超时视作该探针失败，detail 记原因，
        不影响后面的探针继续执行。
        """
        with self._lock:
            probes = [self._probes[name] for name in self._order]
        for probe in probes:
            ok, detail = self._run_probe(probe)
            self.board.record(probe.name, ok, detail)
        return self.board.snapshot()

    def _run_probe(self, probe: Probe) -> Tuple[bool, str]:
        if probe.timeout is None:
            try:
                return True, probe.fn() or ""
            except Exception as exc:
                return False, str(exc)
        outcome: Dict[str, Tuple[bool, str]] = {}

        def target():
            try:
                outcome["result"] = (True, probe.fn() or "")
            except Exception as exc:
                outcome["result"] = (False, str(exc))

        t = threading.Thread(target=target, daemon=True,
                             name=f"healthd-probe-{probe.name}")
        t.start()
        t.join(probe.timeout)
        if t.is_alive():
            return False, f"timeout after {probe.timeout}s"
        return outcome["result"]

    def _passed(self) -> Tuple[int, int]:
        """返回 (通过数, 探针总数)；从未检查过的探针算未通过。"""
        snap = self.board.snapshot()
        with self._lock:
            names = list(self._order)
        passed = sum(1 for n in names if snap.get(n) is not None and snap[n].ok)
        return passed, len(names)

    def status(self) -> str:
        """整体健康状态：ok / degraded / down。"""
        passed, total = self._passed()
        if total == 0 or passed < self.k:
            return STATUS_DOWN
        if passed < total:
            return STATUS_DEGRADED
        return STATUS_OK

    def ready(self) -> bool:
        """能不能接流量：通过探针数达到 k/n 门限（>= k）即可。"""
        passed, total = self._passed()
        return total > 0 and passed >= self.k

    def start(self, period: float, jitter: float = 0.0, clock=None) -> None:
        """起常驻自检线程，每 period 秒跑一轮，周期按 jitter 抖动。

        clock 可注入，需有 sleep(seconds)（可选 now()/wake()），
        默认用真实时钟。重复 start 抛 RuntimeError。
        """
        if period <= 0:
            raise ValueError("period must be positive")
        if jitter < 0:
            raise ValueError("jitter must be >= 0")
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("checker already started")
            self._clock = clock if clock is not None else _RealClock()
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, args=(period, jitter),
                daemon=True, name="healthd-check",
            )
            self._thread.start()

    def stop(self, timeout: Optional[float] = None) -> None:
        """停常驻自检线程并等它退出；未启动时调用无害。"""
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is None:
            return
        self._stop.set()
        wake = getattr(self._clock, "wake", None)
        if wake is not None:
            wake()
        thread.join(timeout)

    def _loop(self, period: float, jitter: float) -> None:
        last = self.status()
        while not self._stop.is_set():
            self.run_once()
            new = self.status()
            if new != last:
                self._notify(last, new)
                last = new
            delay = period
            if jitter:
                delay += random.uniform(-jitter, jitter)
            self._clock.sleep(max(0.0, delay))

    def _notify(self, old: str, new: str) -> None:
        with self._lock:
            callbacks = list(self._on_change)
        for fn in callbacks:
            try:
                fn(old, new)
            except Exception:
                pass
