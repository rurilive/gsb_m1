"""朴素计数累加器。

当前能力：按 label 维度累计样本个数与简单求和，不保留任何时间信息，
因此 count、sum、mean 拿到的都是从进程启动至今的全量口径。
接口覆盖 record、count、sum、mean、labels 与 merge。
纯标准库，无外部依赖，不引入第三方。
"""

DEFAULT_LABEL = "default"


class RateStoreError(ValueError):
    """本模块参数与取值范围错误的基类。"""


class RateStore:
    """按 label 维度累计个数与总和的朴素累加器。

    record(value, label=DEFAULT_LABEL) 记一次样本：该维度个数加一、总和加上 value。
    count(label) 取样本个数，sum(label) 取总和，mean(label) 取平均值，
    labels() 列出出现过的全部维度，merge(other) 把另一份累加器并进来。
    所有查询都只读，改动返回值不影响内部状态。
    """

    def __init__(self):
        self._counts = {}
        self._sums = {}

    def record(self, value, label=DEFAULT_LABEL):
        """累加一次样本，返回 self 便于链式调用。"""
        value = float(value)
        self._counts[label] = self._counts.get(label, 0) + 1
        self._sums[label] = self._sums.get(label, 0.0) + value
        return self

    def count(self, label=DEFAULT_LABEL):
        """该维度已累计的样本个数，未出现过时为 0。"""
        return self._counts.get(label, 0)

    def sum(self, label=DEFAULT_LABEL):
        """该维度已累计的样本总和，未出现过时为 0.0。"""
        return self._sums.get(label, 0.0)

    def mean(self, label=DEFAULT_LABEL):
        """该维度的平均值，个数为 0 时返回 0.0。"""
        n = self.count(label)
        if n == 0:
            return 0.0
        return self.sum(label) / n

    def labels(self):
        """出现过的维度，按字符串升序排列的列表。"""
        return sorted(set(self._counts) | set(self._sums))

    def merge(self, other):
        """把另一份累加器按维度并入自身，返回 self。

        other 必须同样是 RateStore，否则抛 RateStoreError。
        """
        if not isinstance(other, RateStore):
            raise RateStoreError("can only merge another RateStore")
        for label, n in other._counts.items():
            self._counts[label] = self._counts.get(label, 0) + n
        for label, s in other._sums.items():
            self._sums[label] = self._sums.get(label, 0.0) + s
        return self
