"""ratestore: 内存时序指标直方图。

当前只提供一份朴素累加器 RateStore，是滑动窗口分位数直方图改造前的基线。
纯标准库，无外部依赖。
"""

from ratestore.store import DEFAULT_LABEL, RateStore, RateStoreError

__all__ = ["DEFAULT_LABEL", "RateStore", "RateStoreError"]
