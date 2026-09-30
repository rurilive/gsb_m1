"""linbasis.core：异或空间的朴素实现（改造前基线）。

给定一组整数，眼下全是最直白的一条路子：把全部子集枚举出来，逐个算出子集
异或和，再在结果上做统计。

  - max_xor          最大异或和：枚举二的n次方个子集，取异或和里的最大；
  - min_xor          最小异或和：同样枚举全部子集取最小，空子集算零；
  - xor_space_size   不同异或值个数：枚举全部子集算出异或和，放进集合去重；
  - kth_xor          第k小异或和：枚举全部异或和，排序去重后按下标取；
  - can_represent    某数能否由这组数异或表示：枚举全部子集逐个比对；
  - merge_spaces     两组数异或空间的合并：把两组元素拼在一起再枚举。

这些做法直观可靠，结果一眼能看穿，可元素个数一多就是指数级，规模一大就跑
不完。本文件是改造前的基线，朴素路径在改造之后不得删除，新的快速路径必须
与它对同一批输入给出的结果逐项对齐。

异常统一继承 LinbasisErro 基类：InputErro。
"""

_MAX_BITS = 64


class LinbasisErro(Exception):
    """异或空间库所有异常的基类，非法输入与非法操作一律快速失败。"""


class InputErro(LinbasisErro):
    """输入非法：元素不是非负整数、超出位宽、负下标或空集合取第几小。"""


def _as_int(value, where):
    """把入参规整成 Python 整数。布尔不算整数，非法即抛 InputErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputErro("%s：必须是整数，收到 %r" % (where, value))
    return value


def _norm_numbers(numbers):
    """元素序列规整成非负整数元组，逐项校验非负且不超位宽上限。"""
    if numbers is None:
        raise InputErro("元素序列：必须显式给出，不能为 None")
    try:
        items = list(numbers)
    except TypeError:
        raise InputErro("元素序列：必须是可迭代对象，收到 %r" % (numbers,))
    out = []
    for item in items:
        item = _as_int(item, "元素")
        if item < 0:
            raise InputErro("元素：必须是非负整数，收到 %r" % (item,))
        if item >= (1 << _MAX_BITS):
            raise InputErro("元素：超出 %d 位位宽上限，收到 %r" % (_MAX_BITS, item))
        out.append(item)
    return tuple(out)


def _subsets(numbers):
    """枚举全部子集，以元素下标的元组逐条产出，含空子集。"""
    n = len(numbers)
    result = []
    for mask in range(1 << n):
        picked = []
        for i in range(n):
            if mask & (1 << i):
                picked.append(numbers[i])
        result.append(picked)
    return result


def _all_xor_values(numbers):
    """枚举全部子集并逐个求出子集异或和，按子集枚举顺序返回列表。"""
    values = []
    for picked in _subsets(numbers):
        acc = 0
        for value in picked:
            acc ^= value
        values.append(acc)
    return values


class XorSpace:
    """一组整数的异或空间朴素工具集（改造前基线）。

    每条查询开始前把内部计数归零后重新累加：subset_count 数枚举过的子集
    个数，xor_steps 数做过的异或运算次数，供与快速路径的规模对照。
    """

    def __init__(self, numbers):
        self._numbers = _norm_numbers(numbers)
        self.subset_count = 0
        self.xor_steps = 0
        self.numbers = tuple(self._numbers)

    # ----------------------------------------------------------------
    # 最大异或和：枚举全部子集取异或和最大者
    # ----------------------------------------------------------------
    def max_xor(self):
        """返回全部子集异或和里的最大值，空集算零。

        枚举全部子集，逐个子集把元素异或起来，取最大的那个。空集合只有空
        子集一种可能，结果为零。
        """
        self.subset_count = 0
        self.xor_steps = 0
        best = 0
        for picked in _subsets(self._numbers):
            self.subset_count += 1
            acc = 0
            for value in picked:
                acc ^= value
                self.xor_steps += 1
            if acc > best:
                best = acc
        return best

    # ----------------------------------------------------------------
    # 最小异或和：枚举全部子集取异或和最小者
    # ----------------------------------------------------------------
    def min_xor(self):
        """返回全部子集异或和里的最小值，空集算零。

        枚举全部子集逐个取异或和，取最小的那个。空集异或和为零，故最小值
        不会超过零；空集合只有空子集，结果为零。
        """
        self.subset_count = 0
        self.xor_steps = 0
        best = 0
        for picked in _subsets(self._numbers):
            self.subset_count += 1
            acc = 0
            for value in picked:
                acc ^= value
                self.xor_steps += 1
            if acc < best:
                best = acc
        return best

    # ----------------------------------------------------------------
    # 不同异或值个数：枚举全部子集异或和后集合去重
    # ----------------------------------------------------------------
    def xor_space_size(self):
        """返回可以异或出来的不同结果个数，含零在内。

        枚举全部子集逐个求异或和，全部塞进集合去重，集合大小就是答案。空集
        合只能异或出零，结果为一。
        """
        self.subset_count = 0
        self.xor_steps = 0
        seen = set()
        for picked in _subsets(self._numbers):
            self.subset_count += 1
            acc = 0
            for value in picked:
                acc ^= value
                self.xor_steps += 1
            seen.add(acc)
        return len(seen)

    # ----------------------------------------------------------------
    # 第k小异或和：枚举全部异或和排序去重后按下标取
    # ----------------------------------------------------------------
    def kth_xor(self, k):
        """返回第k小的异或和，下标从零起算，零就是最小值。

        枚举全部子集异或和，排序去重得到升序结果，按下标取第k个。k 为负或
        不小于不同异或值个数时抛 InputErro。
        """
        k = _as_int(k, "第几小")
        if k < 0:
            raise InputErro("第几小：不能为负，收到 %r" % (k,))
        self.subset_count = 0
        self.xor_steps = 0
        values = _all_xor_values(self._numbers)
        self.subset_count = len(values)
        self.xor_steps = sum(len(p) for p in _subsets(self._numbers))
        distinct = sorted(set(values))
        if k >= len(distinct):
            raise InputErro("第几小：%r 超出不同异或值个数 %d" % (k, len(distinct)))
        return distinct[k]

    # ----------------------------------------------------------------
    # 能否异或表示：枚举全部子集逐个比对
    # ----------------------------------------------------------------
    def can_represent(self, target):
        """判断 target 能否由这组数的某个子集异或得到。

        枚举全部子集，把每个子集的异或和与 target 比对，命中即返回真。target
        为负抛 InputErro，空集合只能表示零。
        """
        target = _as_int(target, "目标值")
        if target < 0:
            raise InputErro("目标值：必须是非负整数，收到 %r" % (target,))
        self.subset_count = 0
        self.xor_steps = 0
        for picked in _subsets(self._numbers):
            self.subset_count += 1
            acc = 0
            for value in picked:
                acc ^= value
                self.xor_steps += 1
            if acc == target:
                return True
        return False

    # ----------------------------------------------------------------
    # 两组数异或空间的合并：拼接后重新枚举
    # ----------------------------------------------------------------
    def merge_spaces(self, other):
        """返回两组数的并集所构成的新的异或空间工具。

        other 也是一组整数序列，合并口径就是把两组元素原样拼在一起再交给
        新的工具枚举；重复元素照常保留，不影响异或空间的张成。
        """
        try:
            joined = list(self._numbers) + list(other)
        except TypeError:
            raise InputErro("合并：另一组必须是可迭代对象，收到 %r" % (other,))
        return XorSpace(joined)
