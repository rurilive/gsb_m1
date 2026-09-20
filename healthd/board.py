"""状态板：保存每个探针最近一次的检查结果，供健康端点读取。"""

from typing import Dict, Optional


class ProbeResult:
    """单个探针一次检查的结果。ok 为 False 即该探针未通过。"""

    def __init__(self, name: str, ok: bool, detail: str = ""):
        self.name = name
        self.ok = ok
        self.detail = detail

    def __repr__(self):
        return f"ProbeResult(name={self.name!r}, ok={self.ok}, detail={self.detail!r})"


class StatusBoard:
    """按探针名记录最近一次结果。

    record 覆盖同名旧结果；从未检查过的探针不出现在 snapshot 里。
    """

    def __init__(self):
        self._results: Dict[str, ProbeResult] = {}

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self._results[name] = ProbeResult(name, ok, detail)

    def result(self, name: str) -> Optional[ProbeResult]:
        """指定探针的最近结果，没检查过返回 None。"""
        return self._results.get(name)

    def snapshot(self) -> Dict[str, ProbeResult]:
        """返回 {探针名: ProbeResult} 副本，外部改动不影响内部状态。"""
        return dict(self._results)

    def overall_ok(self) -> bool:
        """所有已记录探针都通过才为 True；没有任何记录时为 False。"""
        if not self._results:
            return False
        return all(r.ok for r in self._results.values())
