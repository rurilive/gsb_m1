"""ttlidx: 内存里的朴素字典索引。

当前只有一张永不过期的字典索引，见 ttlidx/index.py。
惰性过期与主动过期、二级倒排索引、原子更新、时间窗扫描与并发清理见任务描述。
"""

from ttlidx.index import DictIndex

__all__ = ["DictIndex"]
