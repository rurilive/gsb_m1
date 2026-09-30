"""朴素异或集合: 一切查询都在一个整数列表上从头到尾线性扫描。

这是改造前的基线实现。内部只保存一个整数列表, 插入是追加, 删除是按值移除,
与给定值异或最大、异或最小都逐元素比较, 集合内任意两数异或最大逐对枚举。
集合一大就随元素个数线性 (枚举则平方) 膨胀。

集合维护的是非负整数, 位宽上限为 MAX_BITS 位, 也就是取值落在 0 到
2**MAX_BITS - 1 之间。并列时的取用口径写死: 与给定值异或最大 (或最小) 时,
若多个元素给出的异或值相同, 取先插入的那个; 集合内两数异或最大只返回数值,
不返回是哪一对。
"""

# 集合允许的位宽上限: 取值必须落在 [0, 2**MAX_BITS)。
MAX_BITS = 30
MAX_VALUE = (1 << MAX_BITS) - 1


class Erro(Exception):
    """本包所有自定义异常的公共基类, 便于调用方统一捕获。"""


class NonNegativeIntError(Erro):
    """元素不是非负整数时抛出。"""


class EmptyCollectionError(Erro):
    """在空集合上做需要元素的查询时抛出。"""


class MissingElementError(Erro):
    """删除一个不存在的元素时抛出。"""


class TooFewElementsError(Erro):
    """集合内不足两个元素却要求两数异或最大时抛出。"""


def _checked(x):
    """校验元素是非负整数且不越位宽; 非法一律抛 NonNegativeIntError。"""
    if isinstance(x, bool) or not isinstance(x, int):
        raise NonNegativeIntError("element must be a non-negative int")
    if x < 0:
        raise NonNegativeIntError("element must be non-negative")
    if x > MAX_VALUE:
        raise NonNegativeIntError("element exceeds MAX_BITS bit width")
    return x


class FlatXorMax:
    """用一个整数列表保存元素, 每次查询都扫全表。

    - add / remove: 把元素追加进列表 / 从列表里按值移除。
    - query_max_xor: 线性找与给定值异或最大的已有元素。
    - query_min_xor: 线性找与给定值异或最小的已有元素。
    - max_pair_xor: 枚举全部元素对求两两异或最大, 平方级。
    """

    def __init__(self, bits=MAX_BITS):
        if not isinstance(bits, int) or isinstance(bits, bool) or bits <= 0:
            raise NonNegativeIntError("bits must be a positive int")
        self._bits = bits
        self._limit = (1 << bits) - 1
        self._items = []

    @property
    def bits(self):
        """返回集合的固定位宽。"""
        return self._bits

    def __len__(self):
        """返回集合中的元素个数 (含重复)。"""
        return len(self._items)

    def __contains__(self, x):
        """判断值等于 x 的元素是否在集合中。"""
        return x in self._items

    def add(self, x):
        """加入元素 x, 可重复加入同一个值, 重复按个数记着。"""
        x = _checked(x)
        if x > self._limit:
            raise NonNegativeIntError("element exceeds collection bit width")
        self._items.append(x)

    def remove(self, x):
        """删除一个值等于 x 的元素; 不存在时抛 MissingElementError。"""
        x = _checked(x)
        for i, v in enumerate(self._items):
            if v == x:
                del self._items[i]
                return
        raise MissingElementError("element not present")

    def values(self):
        """返回当前元素列表的一份拷贝 (按插入顺序)。"""
        return list(self._items)

    def _best(self, x, want_max):
        if not self._items:
            raise EmptyCollectionError("empty collection")
        best = None
        best_val = None
        for v in self._items:
            cur = v ^ x
            if best is None:
                best, best_val = v, cur
                continue
            if (cur > best_val) if want_max else (cur < best_val):
                best, best_val = v, cur
        return best

    def query_max_xor(self, x):
        """返回与 x 异或最大的已有元素; 并列取先插入者; 空集抛 EmptyCollectionError。"""
        x = _checked(x)
        return self._best(x, True)

    def query_min_xor(self, x):
        """返回与 x 异或最小的已有元素; 并列取先插入者; 空集抛 EmptyCollectionError。"""
        x = _checked(x)
        return self._best(x, False)

    def max_pair_xor(self):
        """枚举全部元素对, 返回两两异或最大值; 少于两个元素抛 TooFewElementsError。"""
        if len(self._items) < 2:
            raise TooFewElementsError("need at least two elements")
        best = None
        for i in range(len(self._items)):
            for j in range(i + 1, len(self._items)):
                cur = self._items[i] ^ self._items[j]
                if best is None or cur > best:
                    best = cur
        return best
