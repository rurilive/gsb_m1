"""同步探针运行器：注册探针，手动触发一轮检查并写状态板。"""

from typing import Callable, Dict, List, Optional

from healthd.board import ProbeResult, StatusBoard

ProbeFn = Callable[[], str]


class Probe:
    """一个探针 = 名字 + 检查函数。

    检查函数无参调用：通过则返回细节字符串（可为空），
    失败直接抛异常。
    """

    def __init__(self, name: str, fn: ProbeFn):
        self.name = name
        self.fn = fn


class CheckRunner:
    """按注册顺序串行跑一轮探针，结果写进状态板。

    纯同步、一次性运行，跑不跑、什么时候跑都由调用方决定。
    """

    def __init__(self, board: Optional[StatusBoard] = None):
        self.board = board if board is not None else StatusBoard()
        self._probes: Dict[str, Probe] = {}
        self._order: List[str] = []

    def register(self, name: str, fn: ProbeFn) -> None:
        """注册探针。同名重复注册抛 ValueError。"""
        if name in self._probes:
            raise ValueError(f"probe already registered: {name}")
        self._probes[name] = Probe(name, fn)
        self._order.append(name)

    def names(self) -> List[str]:
        """按注册顺序返回探针名列表副本。"""
        return list(self._order)

    def run_once(self) -> Dict[str, ProbeResult]:
        """按注册顺序串行跑一轮全部探针，返回状态板快照。

        单个探针抛异常视作该探针失败，detail 记异常文本，
        不影响后面的探针继续执行。
        """
        for name in self._order:
            probe = self._probes[name]
            try:
                detail = probe.fn() or ""
                self.board.record(name, True, detail)
            except Exception as exc:
                self.board.record(name, False, str(exc))
        return self.board.snapshot()
