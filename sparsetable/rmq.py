"""区间最值的朴素实现（改造前基线）。

内部只留一个整数列表。每问一次区间，就从头把区间整个扫一遍：
取最小值一回、取最大值一回、取最小值下标又一回，每次各自重扫。
这里没有任何预处理，也没有下标缓存、二维结构或能共享预处理的批量路径。
规模一大，前面扫过的元素就被一遍遍白扫。
"""


class Erro(Exception):
    """本库全部异常的基类。"""


class IllegalArgument(Erro):
    """参数不合格，例如端点为 None、类型不对或下标越界。"""


class NaiveRMQ:
    """朴素静态区间最值。

    持有一个整数序列，查询时对半开区间 [l, r) 逐项扫描：
    ``query_min`` 与 ``query_max`` 分别归约出最小值与最大值，
    ``query_argmin`` 额外记住最小值首次出现的下标。
    空区间返回约定值 ``None``；区间非法抛 ``IllegalArgument``。
    """

    def __init__(self, data):
        if not isinstance(data, (list, tuple)):
            raise IllegalArgument("序列必须是列表或元组")
        for v in data:
            if isinstance(v, bool) or not isinstance(v, int):
                raise IllegalArgument("序列元素必须是整数")
        self._data = [int(v) for v in data]

    # ---- 基本信息 ------------------------------------------------------

    def __len__(self):
        """序列长度。"""
        return len(self._data)

    def value_at(self, i):
        """返回下标 i 处的原始值。"""
        self._check_index(i)
        return self._data[i]

    def as_list(self):
        """返回内部序列的拷贝。"""
        return list(self._data)

    # ---- 区间查询（每次逐项扫描） --------------------------------------

    def query_min(self, l, r):
        """半开区间 [l, r) 上的最小值；空区间返回 None。"""
        self._check_range(l, r)
        if l >= r:
            return None
        best = self._data[l]
        for i in range(l + 1, r):
            if self._data[i] < best:
                best = self._data[i]
        return best

    def query_max(self, l, r):
        """半开区间 [l, r) 上的最大值；空区间返回 None。"""
        self._check_range(l, r)
        if l >= r:
            return None
        best = self._data[l]
        for i in range(l + 1, r):
            if self._data[i] > best:
                best = self._data[i]
        return best

    def query_argmin(self, l, r):
        """半开区间 [l, r) 上最小值首次出现的下标；空区间返回 None。"""
        self._check_range(l, r)
        if l >= r:
            return None
        best_i = l
        best = self._data[l]
        for i in range(l + 1, r):
            if self._data[i] < best:
                best = self._data[i]
                best_i = i
        return best_i

    # ---- 批量 ----------------------------------------------------------

    def query_many(self, ranges):
        """对一批区间逐个求最小值，返回结果列表。

        这里只是把单次查询循环一遍，每个区间依旧各自重扫，
        并没有共享任何预处理。
        """
        out = []
        for l, r in ranges:
            out.append(self.query_min(l, r))
        return out

    # ---- 内部 ----------------------------------------------------------

    def _check_index(self, i):
        if isinstance(i, bool) or not isinstance(i, int):
            raise IllegalArgument("下标必须是整数")
        if i < 0 or i >= len(self._data):
            raise IllegalArgument("下标越界")

    def _check_range(self, l, r):
        for x in (l, r):
            if isinstance(x, bool) or not isinstance(x, int):
                raise IllegalArgument("区间端点必须是整数")
        if l > r:
            raise IllegalArgument("区间左端大于右端")
        if l < 0 or r > len(self._data):
            raise IllegalArgument("区间越界")
