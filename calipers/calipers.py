"""calipers.calipers: 平面点集几何度量的朴素实现（改造前基线）。

围绕一个平面点集做八件最基础的事：

  - convex_hull    凸包：枚举每一对点，看其余点是否都落在它的一侧，
                   以此判定这条有向直线是不是边界，再把边界串成环、
                   去掉落在同一条边内部的共线点；起点取最左下点，
                   顶点按逆时针排列。
  - closest_pair   最近点对：枚举全部点对逐个求距离，取最小。
  - hull_diameter  凸包直径（最远点对）：在凸包顶点上两两配对取最远。
  - min_width      最小宽度：在凸包每条边的朝向下把顶点投影取跨度，套最小值。
  - max_triangle   最大三角形：枚举全部三元组，取面积最大者。
  - circumcircle   外接圆（最小包围圆）：枚举点对与三元组，取能包住全部点、
                   半径最小的那个圆。
  - contains       包含判定：某点是否落在凸包内部或边界上。
  - min_area_rect  最小面积外接矩形：枚举凸包每条边当朝向，逐个投影求
                   轴对齐包围盒，取面积最小者。

这些做法直观可靠，结果一眼能看穿；点一多就平方或立方量级地退化。本文件是
改造前的基线，朴素路径在改造之后不得删除，新实现必须与它对同一批数据给出的
事实逐项对齐。

异常统一继承 CalipersErro 基类：PointSetErro / ClipErro。
"""

import itertools
import math


class CalipersErro(Exception):
    """本工具包所有异常的基类，非法输入与非法操作一律快速失败。"""


class PointSetErro(CalipersErro):
    """点集非法：为空、点数不足、坐标不是有限数。"""


class ClipErro(CalipersErro):
    """包含判定或外接矩形非法：点集不足以定出朝向。"""


_EPS = 1e-9


def _check_point(p, where):
    """把入参规整成 (float, float)，非法即抛 PointSetErro。"""
    try:
        x, y = p
    except (TypeError, ValueError):
        raise PointSetErro("%s: 点必须是二元组，收到 %r" % (where, p))
    for v in (x, y):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise PointSetErro("%s: 坐标必须是实数，收到 %r" % (where, v))
        if not math.isfinite(float(v)):
            raise PointSetErro("%s: 坐标必须是有限数，收到 %r" % (where, v))
    return (float(x), float(y))


def _cross(o, a, b):
    """有向面积的两倍，符号表示 a、b 相对 o 的转向。"""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _dist2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def _between(a, b, p):
    """p 是否严格落在开线段 a-b 内部（要求三点已共线）。"""
    if p[0] < min(a[0], b[0]) or p[0] > max(a[0], b[0]):
        return False
    if p[1] < min(a[1], b[1]) or p[1] > max(a[1], b[1]):
        return False
    return p != a and p != b


def _circum_of(a, b, c):
    """三角形外接圆的 (圆心, 半径平方)；三点共线返回 None。"""
    d = 2.0 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if d == 0.0:
        return None
    a2 = a[0] * a[0] + a[1] * a[1]
    b2 = b[0] * b[0] + b[1] * b[1]
    c2 = c[0] * c[0] + c[1] * c[1]
    ux = (a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d
    uy = (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d
    center = (ux, uy)
    return (center, _dist2(center, a))


class CalipersKit:
    """平面点集几何度量朴素工具集（改造前基线）。"""

    def __init__(self):
        # 各条路径实际发生的枚举规模，进入一次调用前归零后重新累加。
        self.hull_pairs = 0        # 凸包枚举过的点对次数
        self.hull_checks = 0       # 凸包侧判定次数
        self.diameter_pairs = 0    # 直径枚举过的顶点对次数
        self.closest_pairs = 0     # 最近点对枚举过的点对次数
        self.width_checks = 0      # 宽度在每条边朝向下投影的顶点次数
        self.triangle_ops = 0      # 最大三角形枚举过的三元组次数
        self.circle_pairs = 0      # 外接圆枚举过的点对次数
        self.circle_triples = 0    # 外接圆枚举过的三元组次数
        self.rect_edges = 0        # 外接矩形枚举过的朝向（边）数

    # ----------------------------------------------------------------
    # 内部工具
    # ----------------------------------------------------------------
    def _normalize_points(self, points):
        try:
            plist = list(points)
        except TypeError:
            raise PointSetErro("点集必须是可迭代对象，收到 %r" % (points,))
        return [_check_point(p, "点集") for p in plist]

    def _unique(self, points):
        pts = self._normalize_points(points)
        if not pts:
            raise PointSetErro("点集为空")
        return sorted(set(pts))

    def _all_collinear(self, pts):
        """pts 已去重且至少两个点时，判断是否全部共线。"""
        a, b = pts[0], pts[-1]
        for p in pts[1:-1]:
            self.hull_checks += 1
            if _cross(a, b, p) != 0.0:
                return False
        return True

    def _lower_left(self, pts):
        """最先按 y 再按 x 排到最前的点，即最左下点。"""
        return min(pts, key=lambda p: (p[1], p[0]))

    # ----------------------------------------------------------------
    # 凸包：枚举每一对点判定边界，再把边界串成一圈
    # ----------------------------------------------------------------
    def convex_hull(self, points):
        """返回逆时针排列的凸包顶点，起点是最左下点（先比纵坐标再比横坐标）。

        退化约定：空点集抛 PointSetErro；单点返回它自己；去重后全部共线时
        返回最左下与最右上两个端点，最左下在前。落在某条边内部的共线点
        不属于顶点，不会出现在结果里。
        """
        self.hull_pairs = 0
        self.hull_checks = 0
        pts = self._normalize_points(points)
        if not pts:
            raise PointSetErro("凸包：点集为空")
        uniq = sorted(set(pts))
        m = len(uniq)
        if m == 1:
            return [uniq[0]]
        if m == 2 or self._all_collinear(uniq):
            lo = self._lower_left(uniq)
            hi = max(uniq, key=lambda p: (p[1], p[0]))
            return [lo, hi]

        # 有向边 a->b 成立的判据：其余点全在 a->b 左侧或线上，且线段 a-b
        # 内部没有别的点。满足者唯一，记为 a 的后继。
        succ = {}
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                self.hull_pairs += 1
                a, b = uniq[i], uniq[j]
                ok = True
                for k in range(m):
                    if k == i or k == j:
                        continue
                    self.hull_checks += 1
                    c = _cross(a, b, uniq[k])
                    if c < 0.0:
                        ok = False
                        break
                    if c == 0.0 and _between(a, b, uniq[k]):
                        ok = False
                        break
                if ok:
                    succ[i] = j

        start = uniq.index(self._lower_left(uniq))
        order = [start]
        cur = start
        while True:
            nxt = succ.get(cur)
            if nxt is None:
                raise CalipersErro("凸包：边界枚举未闭合，点集可能非法")
            if nxt == start:
                break
            order.append(nxt)
            cur = nxt
            if len(order) > m:
                raise CalipersErro("凸包：边界枚举成环超过点数")

        ring = [uniq[i] for i in order]
        n = len(ring)
        hull = []
        for t in range(n):
            prev = ring[(t - 1) % n]
            mid = ring[t]
            nxt = ring[(t + 1) % n]
            if _cross(prev, mid, nxt) != 0.0:
                hull.append(mid)
        return hull

    # ----------------------------------------------------------------
    # 最近点对：枚举全部点对逐个求距离
    # ----------------------------------------------------------------
    def closest_pair(self, points):
        """返回 (距离平方, (点1, 点2))，点按字典序小的在前。

        并列时取字典序最小的一对。重复点视为不同的点、可给出零距离。
        空点集抛 PointSetErro；单点返回零距离与它自己配自己。
        """
        self.closest_pairs = 0
        pts = sorted(self._normalize_points(points))
        if not pts:
            raise PointSetErro("最近点对：点集为空")
        if len(pts) == 1:
            return (0.0, (pts[0], pts[0]))
        best = None
        bp = None
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                self.closest_pairs += 1
                d2 = _dist2(pts[i], pts[j])
                if best is None or d2 < best:
                    best = d2
                    bp = (pts[i], pts[j])
        return (best, bp)

    # ----------------------------------------------------------------
    # 直径：凸包顶点两两配对全比一遍
    # ----------------------------------------------------------------
    def hull_diameter(self, points):
        """返回 (最远距离平方, (点1, 点2))，端点按字典序小的在前。

        并列时取字典序最小的一对。空点集抛 PointSetErro；单点返回零距离
        与它自己配自己。
        """
        self.diameter_pairs = 0
        hull = self.convex_hull(points)
        h = len(hull)
        if h == 1:
            return (0.0, (hull[0], hull[0]))
        best = None
        bp = None
        for i in range(h):
            for j in range(i + 1, h):
                self.diameter_pairs += 1
                d2 = _dist2(hull[i], hull[j])
                key = (d2, hull[i], hull[j]) if hull[i] <= hull[j] else (d2, hull[j], hull[i])
                if best is None or key[0] > best[0] or (key[0] == best[0] and key[1:] < bp):
                    best = key
                    bp = key[1:]
        return (best[0], bp)

    # ----------------------------------------------------------------
    # 宽度：在凸包每条边的朝向下取最小的法向跨度
    # ----------------------------------------------------------------
    def _width_of_edge(self, hull, i):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length == 0.0:
            return None
        nx, ny = -dy / length, dx / length       # 边 a-b 的法方向
        lo = hi = None
        for p in hull:
            self.width_checks += 1
            v = p[0] * nx + p[1] * ny
            if lo is None or v < lo:
                lo = v
            if hi is None or v > hi:
                hi = v
        return hi - lo

    def min_width(self, points):
        """返回点集宽度：凸包两条平行支撑线的最近距离。

        等价于在全部边朝向下取最小的法向跨度。空点集抛 PointSetErro；
        一点或全部共线退化为零宽度。
        """
        self.width_checks = 0
        hull = self.convex_hull(points)
        h = len(hull)
        if h <= 2:
            return 0.0
        best = None
        for i in range(h):
            w = self._width_of_edge(hull, i)
            if w is not None and (best is None or w < best):
                best = w
        return 0.0 if best is None else best

    # ----------------------------------------------------------------
    # 最大三角形：枚举全部三元组
    # ----------------------------------------------------------------
    def max_triangle(self, points):
        """返回 (最大面积, (顶点1, 顶点2, 顶点3))，三顶点按字典序排列。

        并列时取三顶点字典序最小的那一组。不足三个不同点时面积为零，
        退化为把不同的点补齐到三个。

        空点集抛 PointSetErro。
        """
        self.triangle_ops = 0
        pts = self._unique(points)
        n = len(pts)
        if n < 3:
            if n == 1:
                return (0.0, (pts[0], pts[0], pts[0]))
            return (0.0, (pts[0], pts[0], pts[1]))
        best_area = None
        bp = None
        for tri in itertools.combinations(range(n), 3):
            self.triangle_ops += 1
            a, b, c = pts[tri[0]], pts[tri[1]], pts[tri[2]]
            area = abs(_cross(a, b, c)) / 2.0
            key = (a, b, c) if a <= b <= c else tuple(sorted((a, b, c)))
            if best_area is None or area > best_area or (area == best_area and key < bp):
                best_area = area
                bp = key
        return (best_area, bp)

    # ----------------------------------------------------------------
    # 外接圆：枚举点对与三元组，取包住全部点且半径最小者
    # ----------------------------------------------------------------
    def circumcircle(self, points):
        """返回最小包围圆，字典含 center 与 radius 两项。

        圆心使圆能包住全部点且半径最小；半径并列时取圆心字典序最小者。
        空点集抛 PointSetErro；单点半径为零，圆心即该点。
        """
        self.circle_pairs = 0
        self.circle_triples = 0
        pts = self._unique(points)
        n = len(pts)
        if n == 1:
            return {"center": pts[0], "radius": 0.0}

        cands = []
        for i in range(n):
            for j in range(i + 1, n):
                self.circle_pairs += 1
                a, b = pts[i], pts[j]
                center = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
                cands.append((center, _dist2(center, a)))
        for tri in itertools.combinations(range(n), 3):
            self.circle_triples += 1
            got = _circum_of(pts[tri[0]], pts[tri[1]], pts[tri[2]])
            if got is not None:
                cands.append(got)

        best = None
        for center, r2 in cands:
            if best is not None and r2 > best[0] + _EPS * max(1.0, best[0]):
                continue
            ok = True
            for p in pts:
                if _dist2(center, p) > r2 + _EPS * max(1.0, r2):
                    ok = False
                    break
            if not ok:
                continue
            key = (r2, center)
            if best is None or key < best:
                best = key
        if best is None:
            raise CalipersErro("外接圆：没有找到覆盖全部点的候选圆")
        return {"center": best[1], "radius": math.sqrt(best[0])}

    # ----------------------------------------------------------------
    # 包含判定：某点是否在凸包内部或边界上
    # ----------------------------------------------------------------
    def contains(self, points, q):
        """判断点 q 是否落在点集的凸包内部或边界上，返回布尔值。

        单点与全共线退化时按凸包是点或线段处理；点集为空抛 PointSetErro。
        """
        hull = self.convex_hull(points)
        p = _check_point(q, "待判定点")
        h = len(hull)
        if h == 1:
            return p == hull[0]
        if h == 2:
            a, b = hull[0], hull[1]
            if abs(_cross(a, b, p)) > _EPS:
                return False
            return (min(a[0], b[0]) - _EPS <= p[0] <= max(a[0], b[0]) + _EPS
                    and min(a[1], b[1]) - _EPS <= p[1] <= max(a[1], b[1]) + _EPS)
        for i in range(h):
            a, b = hull[i], hull[(i + 1) % h]
            if _cross(a, b, p) < -_EPS:
                return False
        return True

    # ----------------------------------------------------------------
    # 最小面积外接矩形：枚举凸包每条边当朝向
    # ----------------------------------------------------------------
    def min_area_rect(self, points):
        """返回最小面积外接矩形，字典含 area 与 corners 两项。

        corners 是逆时针的四个角点，朝向取自某条凸包边。面积并列时取
        边序号最小的那个朝向。空点集抛 PointSetErro；一点或全部共线
        退化时面积为零，角点按退化情形给出。
        """
        self.rect_edges = 0
        hull = self.convex_hull(points)
        h = len(hull)
        if h == 1:
            p = hull[0]
            return {"area": 0.0, "corners": [p, p, p, p]}
        if h == 2:
            a, b = hull[0], hull[1]
            return {"area": 0.0, "corners": [a, b, b, a]}

        best = None
        for i in range(h):
            self.rect_edges += 1
            a, b = hull[i], hull[(i + 1) % h]
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy)
            if length == 0.0:
                continue
            ux, uy = dx / length, dy / length       # 主方向
            vx, vy = -uy, ux                        # 法方向
            min_u = max_u = min_v = max_v = None
            for p in hull:
                pu = p[0] * ux + p[1] * uy
                pv = p[0] * vx + p[1] * vy
                if min_u is None:
                    min_u = max_u = pu
                    min_v = max_v = pv
                else:
                    if pu < min_u:
                        min_u = pu
                    if pu > max_u:
                        max_u = pu
                    if pv < min_v:
                        min_v = pv
                    if pv > max_v:
                        max_v = pv
            width = max_u - min_u
            height = max_v - min_v
            area = width * height
            corners = []
            for cu, cv in ((min_u, min_v), (max_u, min_v),
                           (max_u, max_v), (min_u, max_v)):
                corners.append((cu * ux + cv * vx, cu * uy + cv * vy))
            key = (area, i)
            if best is None or key < best[0]:
                best = (key, corners)
        if best is None:
            raise ClipErro("最小面积外接矩形：无法定出凸包朝向")
        return {"area": best[0][0], "corners": best[1]}
