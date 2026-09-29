"""movavg 的现有实现。

这里只有一套朴素的全量平均：每来一个样本就累加一次，平均等于
求和除以个数。样本不被淘汰，时间也不参与计算，因此给不出随时间
变化的速率，给不出分位，内存也会随样本数一直涨。
"""


class Meter:
    """朴素全量平均计数器。

    只做两件确定的事：把样本累加进总量，用总量除以个数得到平均。
    不看时间、不淘汰旧样本、不做分位，也没有窗口概念。
    """

    def __init__(self):
        self._count = 0
        self._total = 0.0

    def record(self, value):
        """记一个样本。value 必须是数值，布尔会被当成数值接受。"""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("value must be a number")
        self._count += 1
        self._total += value

    def mean(self):
        """全部样本的算术平均；还没有样本时返回 0.0。"""
        if self._count == 0:
            return 0.0
        return self._total / self._count

    def count(self):
        """累计记入的样本个数，样本不会被淘汰。"""
        return self._count

    def total(self):
        """全部样本的求和。"""
        return self._total

    def reset(self):
        """清空累计的样本与计数，回到刚建立时的状态。"""
        self._count = 0
        self._total = 0.0
