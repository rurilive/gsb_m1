"""spillkit: 超内存数据的排序去重（溢写 + 多路归并）。"""

from spillkit.merge import merge_runs
from spillkit.runfile import RunFileGuard, RunReader, TooManyOpenRuns, write_run
from spillkit.sorter import SortDeduper, sort_dedup

__all__ = [
    "SortDeduper",
    "sort_dedup",
    "merge_runs",
    "RunFileGuard",
    "RunReader",
    "TooManyOpenRuns",
    "write_run",
]
