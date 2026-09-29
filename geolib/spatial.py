"""geolib.spatial: 二维矩形索引的朴素实现。

当前实现是 FlatIndex：一个矩形列表，每条记录是 (x0, y0, x1, y1, name) 五元组，
其中 (x0, y0) 是左下角，(x1, y1) 是右上角，name 是这条矩形的标识。
所有查询都线性扫描整张列表，矩形一多就白扫。这一层行为由 tests/test_spatial.py 锁住。
"""


class GeoError(Exception):
    """geolib 全部异常的基类。"""


class RectError(GeoError, ValueError):
    """矩形坐标非法，例如左下角大于右上角。"""


def rect_of(rect):
    """把四元组 (x0, y0, x1, y1) 规整成内部五元组用到的坐标部分。

    本函数只做一次合法性检查，返回 (x0, y0, x1, y1) 四个浮点坐标。
    """
    x0, y0, x1, y1 = rect
    x0 = float(x0)
    y0 = float(y0)
    x1 = float(x1)
    y1 = float(y1)
    if x0 > x1 or y0 > y1:
        raise RectError("矩形左下角不得大于右上角: %r" % (rect,))
    return x0, y0, x1, y1


class FlatIndex:
    """朴素矩形索引：一个列表存全部矩形，任何查询都线性扫描。"""

    def __init__(self):
        self._rects = []

    def __len__(self):
        return len(self._rects)

    def insert(self, rect, name):
        """追加一条矩形。rect 是四元组左下右上坐标，name 是标识。"""
        x0, y0, x1, y1 = rect_of(rect)
        self._rects.append((x0, y0, x1, y1, name))
        return name

    def remove(self, name):
        """按标识移除一条矩形，返回被移除的矩形四元组。"""
        for i, item in enumerate(self._rects):
            if item[4] == name:
                del self._rects[i]
                return item[0], item[1], item[2], item[3]
        raise GeoError("未找到标识: %r" % (name,))

    def names(self):
        """按插入顺序返回全部标识。"""
        return [item[4] for item in self._rects]

    def items(self):
        """按插入顺序返回全部 (四元组, 标识)。"""
        return [((r[0], r[1], r[2], r[3]), r[4]) for r in self._rects]

    def contains_point(self, x, y):
        """返回包含点 (x, y) 的全部标识，线性扫描。"""
        x = float(x)
        y = float(y)
        out = []
        for x0, y0, x1, y1, name in self._rects:
            if x0 <= x <= x1 and y0 <= y <= y1:
                out.append(name)
        return out

    def intersect(self, rect):
        """返回与给定矩形相交的全部标识，线性扫描。

        相交口径：两矩形在 x 与 y 两个方向上的投影区间均有重叠，边界接触算相交。
        """
        qx0, qy0, qx1, qy1 = rect_of(rect)
        out = []
        for x0, y0, x1, y1, name in self._rects:
            if x0 <= qx1 and qx0 <= x1 and y0 <= qy1 and qy0 <= y1:
                out.append(name)
        return out

    def nearest(self, x, y):
        """返回距离点 (x, y) 最近的标识，线性扫描。

        距离口径：点到矩形的曼哈顿距离，即 x 与 y 两方向各自到区间的距离之和。
        平局口径：距离相同时返回插入顺序最靠前的标识。空索引返回 None。
        """
        x = float(x)
        y = float(y)
        best = None
        best_d = None
        for x0, y0, x1, y1, name in self._rects:
            dx = 0.0
            if x < x0:
                dx = x0 - x
            elif x > x1:
                dx = x - x1
            dy = 0.0
            if y < y0:
                dy = y0 - y
            elif y > y1:
                dy = y - y1
            d = dx + dy
            if best_d is None or d < best_d:
                best_d = d
                best = name
        return best

    def count(self):
        """返回矩形总数。"""
        return len(self._rects)
