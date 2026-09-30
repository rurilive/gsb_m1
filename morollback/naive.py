"""改造前的朴素区间统计：每个询问都从头把区间扫一遍，规模一大就慢。

对外可见的事实都锁在 tests/test_baseline.py 里：区间压平口径、查询返回的字段、
异常层次以及逐个询问的扫描步数。欲求升级见 README 与任务描述。
"""


class Erro(Exception):
    """本包所有自定义异常的基类。"""


class InvalidArgumentError(Erro):
    """构造参数或调用参数不合法。"""


class InvalidQueryError(Erro):
    """询问本身越界或形状不合法。"""


def _as_int(value, name):
    if isinstance(value, bool):
        raise InvalidArgumentError("参数 %s 必须是整数，收到布尔值" % name)
    if isinstance(value, int):
        return value
    raise InvalidArgumentError("参数 %s 必须是整数，收到 %r" % (name, value))


def normalize_queries(queries):
    """把询问序列规整成二元元组的列表，保持输入次序。

    每个询问是一个左闭右闭区间，写成二元序列；空区间用左端点大于右端点表示
    （规范成 (0, -1)）。元组、列表以外的形状一律拒绝，不静默纠正。
    """
    if queries is None:
        raise InvalidArgumentError("询问序列不得为空引用")
    out = []
    for raw in queries:
        if not isinstance(raw, (tuple, list)):
            raise InvalidQueryError("询问必须是二元序列，收到 %r" % (raw,))
        if len(raw) != 2:
            raise InvalidQueryError("询问必须恰好两个端点，收到 %r" % (raw,))
        left = _as_int(raw[0], "左端点")
        right = _as_int(raw[1], "右端点")
        if left < 0:
            raise InvalidQueryError("左端点不得为负：%r" % (left,))
        if right < -1:
            raise InvalidQueryError("右端点不得小于负一：%r" % (right,))
        if right < left:
            out.append((0, -1))
        else:
            out.append((left, right))
    return out


def prepare(values):
    """记录序列，返回一个不可变口径的记录对象。

    值允许任意可比较的对象（这里是整数），允许重复，允许负数。
    """
    seq = list(values)
    return Prepared(seq)


class Prepared:
    """改造前的记录对象：只存值序列，不做任何预处理。"""

    def __init__(self, seq):
        self.values = seq

    def length(self):
        return len(self.values)


def collapsed_intervals(queries):
    """把区间序列压平成端点列表，按左端点升序、左同则右端点升序。

    返回 [(left, right)]，用于观察排序后的次序；空区间规范为 (0, -1)。
    """
    norm = normalize_queries(queries)
    return sorted(norm, key=lambda pair: (pair[0], pair[1]))


def scan_steps(values, queries):
    """逐条统计扫描步数：每条询问扫过的位置个数之和。

    空区间记零步。返回值是一个整数，用来暴露朴素口径的规模隐患。
    """
    total = 0
    for left, right in normalize_queries(queries):
        if right < left:
            continue
        total += right - left + 1
    return total


class IntervalStats:
    """朴素区间统计器：每个询问都重扫一遍区间内的元素。"""

    def __init__(self, values):
        self.seq = list(values)
        self.n = len(self.seq)

    # -- 内部：把区间内的值收集成列表 ------------------------------------
    def _slice(self, left, right):
        if left < 0:
            raise InvalidQueryError("左端点不得为负：%r" % (left,))
        if right >= self.n:
            raise InvalidQueryError("右端点越界：%r" % (right,))
        if right < left:
            return []
        return self.seq[left:right + 1]

    # -- 能力一：区间内不同值个数 ----------------------------------------
    def query_distinct(self, left, right):
        seen = set()
        for v in self._slice(left, right):
            seen.add(v)
        return len(seen)

    # -- 能力二：区间内出现次数最多的值（并列取最小） --------------------
    def query_mode(self, left, right):
        data = self._slice(left, right)
        if not data:
            return None
        counts = {}
        for v in data:
            counts[v] = counts.get(v, 0) + 1
        best = None
        best_count = -1
        for v in data:
            c = counts[v]
            if c > best_count or (c == best_count and v < best):
                best = v
                best_count = c
        return best

    # -- 能力三：区间内出现次数最多的值的出现次数 ------------------------
    def query_maxfreq(self, left, right):
        mode = self.query_mode(left, right)
        if mode is None:
            return 0
        total = 0
        for v in self._slice(left, right):
            if v == mode:
                total += 1
        return total

    # -- 能力四：区间内某值的出现次数 ------------------------------------
    def query_count(self, left, right, value):
        total = 0
        for v in self._slice(left, right):
            if v == value:
                total += 1
        return total

    # -- 能力五：区间内的极差 --------------------------------------------
    def query_range(self, left, right):
        data = self._slice(left, right)
        if not data:
            return None
        return max(data) - min(data)

    # -- 一条询问的全部指标 ----------------------------------------------
    def answer(self, left, right):
        data = self._slice(left, right)
        return {
            "left": left,
            "right": right,
            "length": len(data),
            "distinct": self.query_distinct(left, right),
            "mode": self.query_mode(left, right),
            "maxfreq": self.query_maxfreq(left, right),
            "range": self.query_range(left, right),
        }

    # -- 一批询问：逐条回答并给出总核对值 --------------------------------
    def run(self, queries):
        answers = []
        checksum = 0
        for left, right in normalize_queries(queries):
            rec = self.answer(left, right)
            answers.append(rec)
            checksum += rec["distinct"]
            checksum += rec["maxfreq"] * 7
            checksum += rec["length"]
            if rec["range"] is not None:
                checksum += rec["range"]
        return answers, checksum
