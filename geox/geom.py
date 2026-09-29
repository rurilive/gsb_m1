"""geox.geom: 平面计算几何朴素实现（改造前基线）。

提供 PlanarGeom，围绕平面点集与线段做四件最基础的事：

  - convex_hull        凸包：逐个点判断谁在谁的外侧（礼物包裹式暴力扫描）；
  - closest_pair       最近点对：两两配对全部比一遍；
  - segments_intersect 线段相交：写成参数方程解一次二元一次方程组；
  - point_in_polygon   点在多边形内：逐边射线法数穿越次数。

这些做法直观可靠，规模小的时候结果一眼能看穿；规模一大就平方级或更差地
退化。本文件是改造前的基线，朴素路径在改造之后不得删除，新实现必须与它
对同一批数据给出的事实逐项对齐。

异常统一继承 GeomError 基类：PointSetError / SegmentError / PolygonError。
"""

import math


class GeomError(Exception):
    """几何工具包所有异常的基类，非法输入与非法操作一律快速失败。"""


class PointSetError(GeomError):
    """点集非法：为空、点数不足、坐标不是有限数。"""


class SegmentError(GeomError):
    """线段非法：端点坐标不是有限数。"""


class PolygonError(GeomError):
    """多边形非法：顶点不足三个、坐标不是有限数。"""


def _check_point(p, where):
    """把入参规整成 (float, float)，非法即抛 PointSetError。"""
    try:
        x, y = p
    except (TypeError, ValueError):
        raise PointSetError("%s: 点必须是二元组，收到 %r" % (where, p))
    for v in (x, y):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise PointSetError("%s: 坐标必须是实数，收到 %r" % (where, v))
        if not math.isfinite(float(v)):
            raise PointSetError("%s: 坐标必须是有限数，收到 %r" % (where, v))
    return (float(x), float(y))


def _cross(o, a, b):
    """有向面积的两倍，符号表示 a、b 相对 o 的转向。"""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _dist2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


class PlanarGeom:
    """平面几何朴素工具集（改造前基线）。"""

    def __init__(self):
        # 两条路径实际发生的比较/判断次数，逐次调用归零后重新累加。
        self.hull_comparisons = 0
        self.closest_comparisons = 0

    # ----------------------------------------------------------------
    # 内部工具
    # ----------------------------------------------------------------
    def _normalize_points(self, points):
        try:
            plist = list(points)
        except TypeError:
            raise PointSetError("点集必须是可迭代对象，收到 %r" % (points,))
        return [_check_point(p, "点集") for p in plist]

    def _all_collinear(self, pts):
        """pts 已去重且至少三个点时，判断是否全部共线。"""
        a, b = pts[0], pts[-1]
        for p in pts[1:-1]:
            self.hull_comparisons += 1
            if _cross(a, b, p) != 0.0:
                return False
        return True

    def _point_on_segment(self, p, a, b):
        """p 是否落在闭线段 a-b 上（含端点），要求三点共线。"""
        if _cross(a, b, p) != 0.0:
            return False
        return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))

    # ----------------------------------------------------------------
    # 凸包：礼物包裹式暴力扫描，每一步都把所有点看一遍找最逆时针的下一点
    # ----------------------------------------------------------------
    def convex_hull(self, points):
        """返回逆时针排列的凸包顶点，起点是字典序最小的点。

        退化约定：空点集抛 PointSetError；单点返回它自己；两点返回两点；
        全部点共线（去重后）时返回字典序最小与最大的两个端点。
        共线中间点不属于顶点，不会出现在结果里。
        """
        self.hull_comparisons = 0
        pts = self._normalize_points(points)
        if not pts:
            raise PointSetError("凸包：点集为空")
        uniq = sorted(set(pts))
        m = len(uniq)
        if m == 1:
            return [uniq[0]]
        if m == 2:
            return [uniq[0], uniq[1]]
        if self._all_collinear(uniq):
            return [uniq[0], uniq[-1]]

        start = uniq[0]
        hull = [start]
        cur = start
        while True:
            nxt = None
            for q in uniq:
                if q == cur:
                    continue
                self.hull_comparisons += 1
                if nxt is None:
                    nxt = q
                    continue
                c = _cross(cur, nxt, q)
                if c < 0.0 or (c == 0.0 and _dist2(cur, q) > _dist2(cur, nxt)):
                    # q 让 cur->nxt 右侧有点，或与 nxt 共线但更远，改选 q
                    nxt = q
            if nxt is None or nxt == start:
                break
            hull.append(nxt)
            cur = nxt
            if len(hull) > m:
                break
        return hull

    # ----------------------------------------------------------------
    # 最近点对：两两配对全部比一遍
    # ----------------------------------------------------------------
    def closest_pair(self, points):
        """返回 (距离, (点1, 点2))。

        按输入次序外层 i、内层 j 枚举 i<j 的点对，严格小于才更新，
        所以距离相同的多组点对里取的是下标字典序最小的一对。
        点数少于两个抛 PointSetError；重合点给出距离 0。
        """
        self.closest_comparisons = 0
        pts = self._normalize_points(points)
        n = len(pts)
        if n < 2:
            raise PointSetError("最近点对：至少需要两个点，收到 %d 个" % n)
        best = None
        bi = bj = -1
        for i in range(n):
            for j in range(i + 1, n):
                self.closest_comparisons += 1
                d2 = _dist2(pts[i], pts[j])
                if best is None or d2 < best:
                    best = d2
                    bi, bj = i, j
        return (math.sqrt(best), (pts[bi], pts[bj]))

    # ----------------------------------------------------------------
    # 线段相交：参数方程 + 共线投影
    # ----------------------------------------------------------------
    def segments_intersect(self, p1, p2, p3, p4):
        """判断闭线段 p1p2 与 p3p4 是否相交，端点为点状线段也成立。

        先解 p1+t(p2-p1) = p3+s(p4-p3)，参数 t、s 同时落在零到一之间即相交；
        平行时再看是否共线，共线则把两条线段投影到同一直线上判断重叠。
        两条线段只有一个端点相碰视为相交。
        """
        a = _check_point(p1, "线段相交")
        b = _check_point(p2, "线段相交")
        c = _check_point(p3, "线段相交")
        d = _check_point(p4, "线段相交")

        if a == b and c == d:
            return a == c
        if a == b:
            return self._point_on_segment(a, c, d)
        if c == d:
            return self._point_on_segment(c, a, b)

        d1 = (b[0] - a[0], b[1] - a[1])
        d2 = (d[0] - c[0], d[1] - c[1])
        r = (c[0] - a[0], c[1] - a[1])
        denom = d1[0] * d2[1] - d1[1] * d2[0]
        if denom != 0.0:
            t = (r[0] * d2[1] - r[1] * d2[0]) / denom
            s = (r[0] * d1[1] - r[1] * d1[0]) / denom
            return 0.0 <= t <= 1.0 and 0.0 <= s <= 1.0
        # 平行：不共线则不可能相交
        if r[0] * d1[1] - r[1] * d1[0] != 0.0:
            return False
        # 共线：把 p3、p4 投影到 p1p2 的参数轴上，看投影区间是否重叠
        len2 = d1[0] * d1[0] + d1[1] * d1[1]
        u3 = (r[0] * d1[0] + r[1] * d1[1]) / len2
        u4 = ((d[0] - a[0]) * d1[0] + (d[1] - a[1]) * d1[1]) / len2
        lo = max(0.0, min(u3, u4))
        hi = min(1.0, max(u3, u4))
        return lo <= hi

    # ----------------------------------------------------------------
    # 点在多边形内：逐边射线法
    # ----------------------------------------------------------------
    def point_in_polygon(self, point, polygon):
        """判断点是否落在多边形内部，边界与顶点视为在内。

        先逐边判断点是否落在某条边上（含顶点），是则直接判为在内；
        否则从该点向正 x 方向引水平射线，逐条边数穿越次数，奇数次即在内。
        自相交多边形不做合法性校验，按穿越奇偶性给出结论。
        顶点不足三个抛 PolygonError。
        """
        p = _check_point(point, "点在多边形内")
        try:
            vlist = list(polygon)
        except TypeError:
            raise PolygonError("点在多边形内：多边形必须是可迭代对象")
        verts = [_check_point(v, "点在多边形内") for v in vlist]
        n = len(verts)
        if n < 3:
            raise PolygonError(
                "点在多边形内：多边形至少需要三个顶点，收到 %d 个" % n)

        for i in range(n):
            if self._point_on_segment(p, verts[i], verts[(i + 1) % n]):
                return True

        inside = False
        px, py = p
        for i in range(n):
            ax, ay = verts[i]
            bx, by = verts[(i + 1) % n]
            if (ay > py) != (by > py):
                xint = ax + (py - ay) * (bx - ax) / (by - ay)
                if px < xint:
                    inside = not inside
        return inside
