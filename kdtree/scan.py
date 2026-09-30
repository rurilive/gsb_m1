"""静态点集上的范围查询与最近邻查询（改造前的朴素基线）。

点集是整数坐标的若干 k 维点。范围查询逐点判定是否落在轴对齐矩形内，
最近邻查询逐点算平方欧氏距离取最小。规模一大就退化成线性扫描，
没有按维度划分的树结构，也没有任何剪枝。
"""


def assert_points(points):
    """校验点集，返回点元组；不合法抛出 ValueError。

    要求：每个点是非空的整数元组；全集各点维度一致且大于零。
    """
    pts = tuple(points)
    if not pts:
        return pts
    dim = len(pts[0])
    if dim <= 0:
        raise ValueError("点的维度必须大于零")
    for p in pts:
        if len(p) != dim:
            raise ValueError("点集内各点维度必须一致")
        for v in p:
            if not isinstance(v, int) or isinstance(v, bool):
                raise ValueError("坐标必须是整数")
    return pts


def assert_box(box, dim):
    """校验轴对齐矩形，返回 (下界, 上界)；不合法抛出 ValueError。

    矩形用两个 k 维序列给出，下界各分量不大于上界各分量。
    """
    if len(box) != 2:
        raise ValueError("矩形必须由下界与上界两项给出")
    low = tuple(box[0])
    high = tuple(box[1])
    if len(low) != dim or len(high) != dim:
        raise ValueError("矩形维度必须与点维度一致")
    for a, b in zip(low, high):
        if a > b:
            raise ValueError("矩形下界不得大于上界")
    return low, high


def inf_norm_sq(p, q):
    """两点各坐标差平方之和，用整数表示，可作距离比较的尺标。"""
    total = 0
    for a, b in zip(p, q):
        d = a - b
        total += d * d
    return total


def in_box(p, low, high):
    """点是否落在闭矩形内，四边都算。"""
    for a, lo, hi in zip(p, low, high):
        if a < lo or a > hi:
            return False
    return True


def points_in_box(points, box):
    """范围查询，返回落在闭矩形内的点的下标，按升序排列。

    朴素做法：逐点判定是否落在矩形内，命中就记下标。矩形两端都算，
    所以贴在边上的点也会算入。
    """
    pts = assert_points(points)
    if not pts:
        return []
    low, high = assert_box(box, len(pts[0]))
    hits = []
    for i, p in enumerate(pts):
        if in_box(p, low, high):
            hits.append(i)
    return hits


def nearest(points, query):
    """最近邻查询，返回 (下标, 平方距离)；空点集返回 None。

    朴素做法：逐点算平方欧氏距离取最小。距离并列时取下标最小的那个。
    全程用整数距离比较，避免浮点。
    """
    pts = assert_points(points)
    if not pts:
        return None
    q = tuple(query)
    if len(q) != len(pts[0]):
        raise ValueError("查询点维度必须与点维度一致")
    best_i = 0
    best_d = inf_norm_sq(pts[0], q)
    for i in range(1, len(pts)):
        d = inf_norm_sq(pts[i], q)
        if d < best_d:
            best_d = d
            best_i = i
    return best_i, best_d
