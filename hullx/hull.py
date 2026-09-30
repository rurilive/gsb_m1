"""hullx.hull: 平面点集凸包的朴素实现（改造前基线）。

围绕平面点集做三件最基础的事：

  - convex_hull       凸包：枚举每一对点，看其余点是否都落在其一侧，
                      以此判定这条有向直线是不是一条边界；再把边界串成环，
                      最后把落在同一条直线上的中间点去掉；
  - diameter          直径：在凸包顶点上两两配对，全部比一遍取最远点对；
  - min_bounding_rect 最小外接矩形：在凸包顶点上枚举全部顶点对当作候选朝向，
                      逐个把凸包投影到该朝向下求包围盒，取面积最小者。

这些做法直观可靠，结果一眼能看穿；点一多就立方或平方量级地退化。本文件是
改造前的基线，朴素路径在改造之后不得删除，新实现必须与它对同一批数据给出的
事实逐项对齐。

异常统一继承 HullErro 基类：PointSetErro / RectErro。
"""

import math


class HullErro(Exception):
    """凸包工具包所有异常的基类，非法输入与非法操作一律快速失败。"""


class PointSetErro(HullErro):
    """点集非法：为空、点数不足、坐标不是有限数。"""


class RectErro(HullErro):
    """外接矩形非法：点集不足以定出朝向。"""


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


class HullKit:
    """平面点集凸包朴素工具集（改造前基线）。"""

    def __init__(self):
        # 各条路径实际发生的判断/配对次数，进入一次调用前归零后重新累加。
        self.hull_pairs = 0
        self.hull_side_checks = 0
        self.diameter_pairs = 0
        self.rect_pairs = 0
        self.rect_point_checks = 0

    # ----------------------------------------------------------------
    # 内部工具
    # ----------------------------------------------------------------
    def _normalize_points(self, points):
        try:
            plist = list(points)
        except TypeError:
            raise PointSetErro("点集必须是可迭代对象，收到 %r" % (points,))
        return [_check_point(p, "点集") for p in plist]

    def _all_collinear(self, pts):
        """pts 已去重且至少三个点时，判断是否全部共线。"""
        a, b = pts[0], pts[-1]
        for p in pts[1:-1]:
            self.hull_side_checks += 1
            if _cross(a, b, p) != 0.0:
                return False
        return True

    # ----------------------------------------------------------------
    # 凸包：枚举每一对点判定边界，再把边界串成一圈
    # ----------------------------------------------------------------
    def convex_hull(self, points):
        """返回逆时针排列的凸包顶点，起点是字典序最小的点。

        退化约定：空点集抛 PointSetErro；单点返回它自己；两点返回两点；
        全部点共线（去重后）时返回字典序最小与最大的两个端点。
        落在某条边内部的共线点不属于顶点，不会出现在结果里。
        """
        self.hull_pairs = 0
        self.hull_side_checks = 0
        pts = self._normalize_points(points)
        if not pts:
            raise PointSetErro("凸包：点集为空")
        uniq = sorted(set(pts))
        m = len(uniq)
        if m == 1:
            return [uniq[0]]
        if m == 2:
            return [uniq[0], uniq[1]]
        if self._all_collinear(uniq):
            return [uniq[0], uniq[-1]]

        # 有向边 a->b 成立的判据：其余点全在 a->b 左侧或线上，且线段
        # a-b 内部没有别的点。满足者唯一，记为 a 的后继。
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
                    self.hull_side_checks += 1
                    c = _cross(a, b, uniq[k])
                    if c < 0.0:
                        ok = False
                        break
                    if c == 0.0 and _between(a, b, uniq[k]):
                        ok = False
                        break
                if ok:
                    succ[i] = j

        # 字典序最小的点必是顶点，从它出发沿后继走一圈。
        start = 0
        order = [start]
        cur = start
        while True:
            nxt = succ.get(cur)
            if nxt is None:
                raise HullErro("凸包：边界枚举未闭合，点集可能非法")
            if nxt == start:
                break
            order.append(nxt)
            cur = nxt
            if len(order) > m:
                raise HullErro("凸包：边界枚举成环超过点数")

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
    # 直径：凸包顶点两两配对全比一遍
    # ----------------------------------------------------------------
    def diameter(self, points):
        """返回 (最远距离, (点1, 点2))，在凸包顶点上两两配对取最远。

        平局取顶点下标字典序最小的一对（凸包起点为字典序最小的点）。
        空点集抛 PointSetErro；单点返回零距离与它自己配自己。
        """
        self.diameter_pairs = 0
        hull = self.convex_hull(points)
        h = len(hull)
        if h == 1:
            return (0.0, (hull[0], hull[0]))
        best = None
        bp = (-1, -1)
        for i in range(h):
            for j in range(i + 1, h):
                self.diameter_pairs += 1
                d2 = _dist2(hull[i], hull[j])
                if best is None or d2 > best:
                    best = d2
                    bp = (i, j)
        return (math.sqrt(best), (hull[bp[0]], hull[bp[1]]))

    # ----------------------------------------------------------------
    # 最小外接矩形：枚举全部顶点对当朝向，逐个投影求包围盒
    # ----------------------------------------------------------------
    def min_bounding_rect(self, points):
        """返回最小面积外接矩形。

        结果字典含 area、width、height、corners、angle 五项：
        width 是所选朝向下主方向的跨度，height 是法方向跨度，
        两者之积即面积；corners 是逆时针的四个角点；angle 是主方向角度，
        取值落在零到圆周率之间。面积相同时取顶点下标字典序最小的那一对。

        空点集抛 PointSetErro；一个点或两个点（含全共线退化）给出零面积
        的退化矩形，不去枚举朝向。
        """
        self.rect_pairs = 0
        self.rect_point_checks = 0
        hull = self.convex_hull(points)
        h = len(hull)
        if h == 1:
            p = hull[0]
            return {"area": 0.0, "width": 0.0, "height": 0.0,
                    "corners": [p, p, p, p], "angle": 0.0}
        if h == 2:
            a, b = hull[0], hull[1]
            side = math.sqrt(_dist2(a, b))
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            return {"area": 0.0, "width": side, "height": 0.0,
                    "corners": [a, b, b, a], "angle": ang}

        best = None
        for i in range(h):
            for j in range(i + 1, h):
                self.rect_pairs += 1
                ax, ay = hull[i]
                bx, by = hull[j]
                dx, dy = bx - ax, by - ay
                if dx == 0.0 and dy == 0.0:
                    continue
                length = math.sqrt(dx * dx + dy * dy)
                ux, uy = dx / length, dy / length       # 主方向
                vx, vy = -uy, ux                        # 法方向
                min_u = max_u = min_v = max_v = None
                for p in hull:
                    self.rect_point_checks += 1
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
                if (best is None or area < best["area"]
                        or (area == best["area"] and (i, j) < best["ij"])):
                    # 四个角在旋转坐标系里是轴对齐包围盒，再变换回原坐标。
                    corners = []
                    for cu, cv in ((min_u, min_v), (max_u, min_v),
                                   (max_u, max_v), (min_u, max_v)):
                        corners.append((cu * ux + cv * vx, cu * uy + cv * vy))
                    best = {"area": area, "width": width, "height": height,
                            "corners": corners,
                            "angle": math.atan2(uy, ux), "ij": (i, j)}
        if best is None:
            raise RectErro("最小外接矩形：无法定出凸包朝向")
        del best["ij"]
        return best

    # ----------------------------------------------------------------
    # 宽度：在全部顶点对朝向下取最小的法向跨度
    # ----------------------------------------------------------------
    def width(self, points):
        """返回点集宽度：最小外接矩形里两条平行支撑线的最近距离。

        等价于在全部朝向里取最小的法向跨度，即最小外接矩形的 height 最小值。
        空点集抛 PointSetErro；一点或两点退化为零宽度。
        """
        rect = self.min_bounding_rect(points)
        return rect["height"]
