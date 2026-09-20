"""探针运行器：注册探针，手动或常驻定期跑检查并写状态板。

探针可带 timeout：超时未返回直接判该探针失败，不会拖死整轮。
整体状态分三档：全部通过 OK，通过数达到门限 k 但未全过 DEGRADED，
否则 DOWN。ready() 按 k/n 门限回答能不能接流量。
常驻模式下 start()/stop() 起停一个后台检查线程，周期带随机抖动，
时钟可注入，状态翻转时在检查线程内回调 on_change 注册的函数。
"""

import random
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from healthd.board import ProbeResult, StatusBoard

ProbeFn = Callable[[], str]

OK = "ok"
DEGRADED = "degraded"
DOWN = "down"
STATES = (OK, DEGRADED, DOWN)


class MonotonicClock:
    """默认时钟：单调时间 + 可被事件提前唤醒的睡眠。"""

    def time(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float, stop_event: Optional[threading.Event] = None) -> None:
        """睡 seconds，stop_event 被置位时提前返回。"""
        if stop_event is None:
            time.sleep(seconds)
        else:
            stop_event.wait(seconds)


class Probe:
    """一个探针 = 名字 + 检查函数。

    检查函数无参调用：通过则返回细节字符串（可为空），
    失败直接抛异常。
    """

    def __init__(self, name: str, fn: ProbeFn, timeout: Optional[float] = None):
        self.name = name
        self.fn = fn
        self.timeout = timeout


class CheckRunner:
    """跑探针、写状态板：可手动 run_once()，也可 start() 常驻定期跑。

    手动模式跑不跑、什么时候跑由调用方决定；常驻模式由后台线程按
    抖动周期自动跑，探针超时、状态翻转回调都不影响线程存活。
    """

    def __init__(
        self,
        board: Optional[StatusBoard] = None,
        period: float = 10.0,
        jitter: float = 0.0,
        k: Optional[int] = None,
        clock=None,
        rng: Optional[random.Random] = None,
    ):
        """period 秒一轮，实际间隔在 [period-jitter, period+jitter] 间抖动；
        k 是就绪门限（默认 1，至少 1 个探针通过才接流量）；
        clock 需提供 time() 和 sleep(seconds)，不传用单调墙钟。
        """
        self.board = board if board is not None else StatusBoard()
        self._probes: Dict[str, Probe] = {}
        self._order: List[str] = []
        self.period = period
        self.jitter = jitter
        self.k = k if k is not None else 1
        self._clock = clock if clock is not None else MonotonicClock()
        self._rng = rng if rng is not None else random.Random()
        self._reg_lock = threading.RLock()
        self._round_lock = threading.Lock()
        self._change_lock = threading.RLock()
        self._change_fns: List[Callable[[str, str], None]] = []
        self._last_status = DOWN
        self._thread: Optional[threading.Thread] = None
        self._stop_event: Optional[threading.Event] = None

    def register(self, name: str, fn: ProbeFn, timeout: Optional[float] = None) -> None:
        """注册探针。同名重复注册抛 ValueError。"""
        if timeout is not None and timeout <= 0:
            raise ValueError(f"timeout must be positive: {timeout}")
        with self._reg_lock:
            if name in self._probes:
                raise ValueError(f"probe already registered: {name}")
            self._probes[name] = Probe(name, fn, timeout)
            self._order.append(name)

    def names(self) -> List[str]:
        """按注册顺序返回探针名列表副本。"""
        with self._reg_lock:
            return list(self._order)

    def run_once(self) -> Dict[str, ProbeResult]:
        """按注册顺序串行跑一轮全部探针，返回状态板快照。

        单个探针抛异常视作该探针失败，detail 记异常文本，
        不影响后面的探针继续执行。
        """
        with self._round_lock:
            with self._reg_lock:
                probes = [self._probes[name] for name in self._order]
            for probe in probes:
                ok, detail = self._run_probe(probe)
                self.board.record(probe.name, ok, detail)
        return self.board.snapshot()

    def _run_probe(self, probe: Probe) -> Tuple[bool, str]:
        """跑单个探针。没设 timeout 时直接在本线程调用（与基线一致）；
        设了 timeout 放到守护线程里跑，时限内没返回即判失败，
        卡死的线程随进程退出，不影响后续探针和下一轮。
        """
        if probe.timeout is None:
            try:
                return True, probe.fn() or ""
            except Exception as exc:
                return False, str(exc)

        box: Dict[str, object] = {}

        def target():
            try:
                box["detail"] = probe.fn() or ""
            except Exception as exc:  # noqa: BLE001 - 探针异常一律判失败
                box["error"] = exc

        worker = threading.Thread(
            target=target, name=f"healthd-probe-{probe.name}", daemon=True
        )
        worker.start()
        worker.join(probe.timeout)
        if worker.is_alive():
            return False, f"timeout after {probe.timeout}s"
        if "error" in box:
            return False, str(box["error"])
        return True, str(box.get("detail", ""))

    def _counts(self) -> Tuple[int, int]:
        """返回 (通过数, 已检查数)。只统计注册过且已出结果的探针。"""
        snap = self.board.snapshot()
        with self._reg_lock:
            names = set(self._order)
        passed = sum(1 for name, r in snap.items() if name in names and r.ok)
        return passed, len(names)

    def status(self) -> str:
        """整体状态：全过 OK；达到门限 k 但没全过 DEGRADED；否则 DOWN。
        还没跑过任何一轮（没有任何记录）时为 DOWN。
        """
        passed, total = self._counts()
        if total == 0 or not self.board.snapshot():
            return DOWN
        if passed == total:
            return OK
        if passed >= self.k:
            return DEGRADED
        return DOWN

    def ready(self) -> bool:
        """能否接流量：通过探针数达到门限 k 即可（OK 或 DEGRADED）。"""
        passed, total = self._counts()
        return total > 0 and passed >= self.k

    def on_change(self, fn: Callable[[str, str], None]) -> None:
        """注册整体状态翻转回调 fn(old, new)，在检查线程内同步调用；
        回调抛异常只记下来，不中断后续检查。start 之前、之后注册均可。
        """
        with self._change_lock:
            self._change_fns.append(fn)

    def _next_delay(self) -> float:
        if self.jitter <= 0:
            return self.period
        low = max(0.0, self.period - self.jitter)
        high = self.period + self.jitter
        return self._rng.uniform(low, high)

    def start(self) -> None:
        """起后台自检线程：立即跑第一轮，之后每抖动周期一轮。重复起抛错。"""
        with self._reg_lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("healthd check loop already running")
            self._stop_event = threading.Event()
            stop_event = self._stop_event
            self._last_status = DOWN
            thread = threading.Thread(target=self._loop, args=(stop_event,),
                                      name="healthd-checker", daemon=True)
            self._thread = thread
        thread.start()

    def stop(self) -> None:
        """停自检线程，等当前轮跑完；可重复调用。"""
        with self._reg_lock:
            thread = self._thread
            stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join()

    def _loop(self, stop_event: threading.Event) -> None:
        while True:
            try:
                self.run_once()
                self._publish_change()
            except Exception as exc:  # noqa: BLE001 - 检查线程不能死
                print(f"healthd: check round failed: {exc!r}")
            if stop_event.is_set():
                return
            delay = self._next_delay()
            self._clock.sleep(delay, stop_event)

    def _publish_change(self) -> None:
        new_status = self.status()
        with self._change_lock:
            old_status = self._last_status
            if new_status == old_status:
                return
            self._last_status = new_status
            fns = list(self._change_fns)
        for fn in fns:
            try:
                fn(old_status, new_status)
            except Exception as exc:  # noqa: BLE001 - 回调错误不中断检查
                print(f"healthd: on_change callback failed: {exc!r}")
