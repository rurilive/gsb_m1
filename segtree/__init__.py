"""segtree：一个纯标准库的区间统计小仓库。

当前只有一个朴素区间数组实现，见 segtree.range。
"""

from .range import SegError, RangeArray

__all__ = ["SegError", "RangeArray"]
