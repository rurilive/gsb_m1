"""半平面交（改造前的朴素基线）。

半平面用有向直线表示：直线经过两点 a、b，内侧是直线左侧。
基线对每一对边界直线求交点，再拿候选交点逐条判定是否落在所有半平面内，
通过的点交给凸包，最后算多边形面积。顶点一多就是平方到立方量级。
所有运算走整数叉积与有理数，不碰浮点。
"""

from fractions import Fraction


def _as_fraction(x):
    """把输入坐标统一成有理数，避免任何浮点参与。"""
    if isinstance(x, Fraction):
        return x
    return Fraction(x)


def _point(p):
    """把二元坐标转成有理数点。"""
    return (_as_fraction(p[0]), _as_fraction(p[1]))


def _cross(o, a, b):
    """有向叉积：oa 与 ob 的叉积，符号表示转向。"""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


class HalfPlane:
    """有向直线 a 到 b 左侧的半平面，含边界。

    a、b 为两个不同的二元坐标；两点重合视为非法，直接抛 ValueError。
    内侧判据用叉积大于等于零表示，不含任何浮点。
    """

    def __init__(self, a, b):
        pa = _point(a)
        pb = _point(b)
        if pa == pb:
            raise ValueError("半平面的两个定义点不能重合")
        self._a = pa
        self._b = pb

    @property
    def a(self):
        """定义点 a。"""
        return self._a

    @property
    def b(self):
        """定义点 b。"""
        return self._b

    def direction(self):
        """从 a 指向 b 的方向向量。"""
        return (self._b[0] - self._a[0], self._b[1] - self._a[1])

    def contains(self, p):
        """点 p 是否落在半平面内，含边界。"""
        q = _point(p)
        return _cross(self._a, self._b, q) >= 0

    def __repr__(self):
        return "HalfPlane(%r, %r)" % (self._a, self._b)


def line_intersection(h1, h2):
    """两条有向直线所在直线的交点；两线平行时返回 None。

    用参数方程与整数行列式求解，t 用有理数表示，结果精确。
    """
    a1, b1 = h1.a, h1.b
    a2, b2 = h2.a, h2.b
    d1 = (b1[0] - a1[0], b1[1] - a1[1])
    d2 = (b2[0] - a2[0], b2[1] - a2[1])
    denom = d1[0] * d2[1] - d1[1] * d2[0]
    if denom == 0:
        return None
    dx = a2[0] - a1[0]
    dy = a2[1] - a1[1]
    t = Fraction(dx * d2[1] - dy * d2[0], denom)
    return (a1[0] + t * d1[0], a1[1] + t * d1[1])


def convex_hull(points):
    """对点集求凸包，返回逆时针排列的顶点，不含重复的起点。

    采用最直白的单调链写法：先排序，再分别扫出下包与上包。
    共线的中间点会被丢掉；点数不足三时原样返回去重排序的结果。
    """
    pts = sorted(set(_point(p) for p in points))
    if len(pts) <= 1:
        return list(pts)

    def _chain(seq):
        chain = []
        for p in seq:
            while len(chain) >= 2 and _cross(chain[-2], chain[-1], p) <= 0:
                chain.pop()
            chain.append(p)
        return chain

    lower = _chain(pts)
    upper = _chain(reversed(pts))
    return lower[:-1] + upper[:-1]


def polygon_area(vertices):
    """鞋带公式求多边形面积，取非负；点数不足三返回零。"""
    pts = [_point(p) for p in vertices]
    if len(pts) < 3:
        return Fraction(0)
    acc = Fraction(0)
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        acc += x1 * y2 - x2 * y1
    return abs(acc) / 2


class RegionResult:
    """半平面交的结果：顶点序列与面积。

    vertices 逆时针排列，首尾不重复；area 为非负有理数。
    """

    def __init__(self, vertices, area):
        self.vertices = tuple(vertices)
        self.area = area

    def __eq__(self, other):
        if not isinstance(other, RegionResult):
            return NotImplemented
        return self.vertices == other.vertices and self.area == other.area

    def __repr__(self):
        return "RegionResult(vertices=%r, area=%r)" % (self.vertices, self.area)


def intersect(halfplanes):
    """求半平面交，返回 RegionResult。

    朴素做法：枚举每一对边界直线的交点，保留落在所有半平面内的点，
    再做凸包求面积。对完全有界且非退化的交多边形，结果正确；
    交为空、退化成点或线段、或者无界时，这套枚举判不出正确形态。
    """
    hps = list(halfplanes)
    candidates = []
    for i in range(len(hps)):
        for j in range(i + 1, len(hps)):
            p = line_intersection(hps[i], hps[j])
            if p is None:
                continue
            if all(h.contains(p) for h in hps):
                candidates.append(p)
    verts = convex_hull(candidates)
    return RegionResult(verts, polygon_area(verts))
