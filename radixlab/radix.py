"""radixlab.radix：非比较排序的朴素基线实现。

现状实现全部走最直白的路子，规模一大就退化成依赖比较排序，但结果正确、口径固定：

  - 非负整数排序：直接把整列交给内置排序，不显式按位分桶；
  - 十进制位分桶：从低位到高位各趟，先用逐元素求位数字统计各桶，再借助内置
    稳定排序按当前位收回，位不够补零，结果与非负整数排序一致；
  - 二进制位分桶：按固定位宽把每趟要看的位取低位一半与高位一半两趟，仍借助
    内置排序，结果与十进制位分桶一致；
  - 某位众数与分桶计数：对每个元素用循环除十逐次取余求出该位数字，再逐个桶
    统计，众数并列时取较小的数字。

求第几位用循环除十逐次取余，负数与超过取值上限的输入直接判为非法。整套口径
连同边界都被 tests 目录下的基线测试锁住。
"""


class RadixError(Exception):
    """radixlab 全部异常的基类。"""


class RadixInputError(RadixError):
    """输入数据不合法：不是整数序列、元素为负、元素超过取值上限、位序号为负、
    基数不合适、尚未载入等。"""


# 取值上限：超过它按超范围输入直接判非法。
MAX_VALUE = 10 ** 18


def _check_int(name, value):
    """必须是整数，且不是布尔值。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise RadixInputError("%s 必须是整数" % (name,))


def _digit_division(value, pos):
    """求 value 在第 pos 位上的十进制数字。

    朴素口径：循环除十逐次取余，pos 为零时看个位。pos 为负立即失败。负数与
    超范围输入直接判非法。
    """
    if pos < 0:
        raise RadixInputError("位序号不能为负")
    if value < 0:
        raise RadixInputError("负数不合法")
    if value > MAX_VALUE:
        raise RadixInputError("数值超过取值上限")
    n = value
    p = pos
    while p > 0:
        n = n // 10
        p -= 1
    return n % 10


class NaiveRadix:
    """非负整数序列的朴素排序与分桶工具。

    load(values) 载入一批非负整数；多次 load 整体替换上一批。
    """

    def __init__(self):
        self._values = None
        self._comparisons = 0
        self._placements = 0

    # ------------------------------------------------------------------ 载入
    def load(self, values):
        """登记一批非负整数。不是整数序列、元素为负或超过取值上限都抛
        RadixInputError。"""
        if not isinstance(values, (list, tuple)):
            raise RadixInputError("输入必须是列表或元组")
        out = []
        for item in values:
            _check_int("元素", item)
            if item < 0:
                raise RadixInputError("负数不合法")
            if item > MAX_VALUE:
                raise RadixInputError("数值超过取值上限")
            out.append(item)
        self._values = out
        self._comparisons = 0
        self._placements = 0

    def _loaded(self):
        if self._values is None:
            raise RadixInputError("尚未载入数据，请先调用 load")
        return self._values

    def values(self):
        """原始序列的副本，输入保持不变。"""
        return list(self._loaded())

    # ------------------------------------------------------------------ 计数
    def _sort_cost(self, count):
        """把一趟内置排序按比较排序口径折算出的比较次数，规模越大增长越快。"""
        if count < 2:
            return 0
        steps = 0
        size = count
        while size > 1:
            size = (size + 1) // 2
            steps += 1
        return count * steps

    def comparison_count(self):
        """迄今累计的元素间比较次数（朴素口径的估算）。"""
        self._loaded()
        return self._comparisons

    def placement_count(self):
        """迄今累计的按位分桶分配次数。"""
        self._loaded()
        return self._placements

    def reset_counts(self):
        """把两类计数清零，便于分段对照。"""
        self._loaded()
        self._comparisons = 0
        self._placements = 0

    # -------------------------------------------------------- 位数与排序
    def width(self):
        """十进制位宽，空序列返回一，全部为零返回一。"""
        values = self._loaded()
        if not values:
            return 1
        biggest = max(values)
        w = 1
        while biggest >= 10:
            biggest = biggest // 10
            w += 1
        return w

    def bit_width(self):
        """二进制位宽，空序列返回一，全部为零返回一。"""
        values = self._loaded()
        if not values:
            return 1
        biggest = max(values)
        b = 1
        while (1 << b) <= biggest:
            b += 1
        return b

    def half_width(self):
        """二进制低位一半与高位一半各占的位宽，至少为一。"""
        return max(1, (self.bit_width() + 1) // 2)

    def comparison_sorted(self):
        """内置排序给出的非降序序列，作为对照基准。"""
        values = self._loaded()
        out = sorted(values)
        self._comparisons += self._sort_cost(len(out))
        return out

    def lowdigit_path(self):
        """从低位到高位逐位分桶排序，结果与非降序一致。

        现场朴素口径：先把整列交给内置排序，再对每一趟用逐元素求位数字统计各桶，
        接着借助内置的稳定排序按当前位收回。位不够的短数按补零处理，低于当前位
        的部分视为零。每个元素在每一趟都被求一次位数字。
        """
        values = self._loaded()
        out = sorted(values)
        self._comparisons += self._sort_cost(len(out))
        for pos in range(self.width()):
            buckets = {}
            for item in out:
                d = _digit_division(item, pos)
                buckets[d] = buckets.get(d, 0) + 1
            self._placements += len(out)
            out = sorted(out, key=lambda item: _digit_division(item, pos))
            self._comparisons += self._sort_cost(len(out))
        return out

    def highdigit_path(self):
        """按固定二进制位宽分两趟排序，低位一半在前、高位一半在后。

        现场朴素口径：先把整列交给内置排序，再按低位一半与高位一半各收回一趟，
        每趟借助内置的稳定排序，位不够的短数高位补零。结果与十进制位分桶一致。
        """
        values = self._loaded()
        out = sorted(values)
        self._comparisons += self._sort_cost(len(out))
        half = self.half_width()
        mask = (1 << half) - 1
        for shift in (0, half):
            self._placements += len(out)
            out = sorted(out, key=lambda item: (item >> shift) & mask)
            self._comparisons += self._sort_cost(len(out))
        return out

    # ---------------------------------------------------- 某位众数与分桶
    def digit_histogram(self, pos):
        """第 pos 位上各个数字出现的次数，形如 数字 到 次数 的映射。

        现场朴素口径：对每个元素用循环除十逐次取余求出该位数字再累计。
        """
        values = self._loaded()
        if pos < 0:
            raise RadixInputError("位序号不能为负")
        hist = {}
        for item in values:
            d = _digit_division(item, pos)
            hist[d] = hist.get(d, 0) + 1
        self._placements += len(values)
        return hist

    def bucket_counts(self, pos):
        """按第 pos 位分桶，返回各个桶里的元素个数。

        现场朴素口径：与直方图同口径，逐元素求位数字后累计。
        """
        return self.digit_histogram(pos)

    def modal_digit(self, pos):
        """第 pos 位上出现次数最多的数字，并列时取较小的数字。

        现场朴素口径：先逐元素求出该位数字，再逐个数字比较次数取最大。
        """
        hist = self.digit_histogram(pos)
        best_digit = 0
        best_count = -1
        for d in range(10):
            count = hist.get(d, 0)
            if count > best_count:
                best_count = count
                best_digit = d
        self._placements += 10
        return best_digit

    def is_sorted(self, sequence):
        """判断给定序列是否非降序，纯判定不改计数。"""
        if not isinstance(sequence, (list, tuple)):
            raise RadixInputError("待判序列必须是列表或元组")
        for i in range(len(sequence) - 1):
            if sequence[i] > sequence[i + 1]:
                return False
        return True

    def check_sorted(self):
        """判断已载入序列是否本身非降序。"""
        return self.is_sorted(self._loaded())
