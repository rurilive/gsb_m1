"""栅格地图：尺寸、障碍、邻居枚举与步长。

坐标 (x, y) 为整数，x 向右、y 向上，原点在左下角。
八方向移动：横竖一步代价 1.0，斜一步代价 math.sqrt(2)。
斜穿墙角（两侧正交邻格都不可通行）不允许，贴着单侧障碍滑过去可以。
"""

import math

SQRT2 = math.sqrt(2.0)

# 邻居枚举顺序固定：东、东北、北、西北、西、西南、南、东南。
DIRECTIONS = (
    (1, 0), (1, 1), (0, 1), (-1, 1),
    (-1, 0), (-1, -1), (0, -1), (1, -1),
)


class GridError(ValueError):
    """坐标越界、地图参数非法或端点不可通行。"""


class Grid:
    """障碍用阻塞格集合表示的二维栅格。"""

    def __init__(self, width, height, blocked=()):
        if not isinstance(width, int) or not isinstance(height, int):
            raise GridError("width and height must be ints")
        if width <= 0 or height <= 0:
            raise GridError("width and height must be positive")
        self.width = width
        self.height = height
        self._blocked = set()
        for cell in blocked:
            x, y = cell
            self._check(x, y)
            self._blocked.add((x, y))

    # -- 查询 --------------------------------------------------

    def in_bounds(self, x, y):
        """(x, y) 是否落在地图范围内。"""
        return 0 <= x < self.width and 0 <= y < self.height

    def _check(self, x, y):
        if not self.in_bounds(x, y):
            raise GridError("cell (%r, %r) out of bounds" % (x, y))

    def is_blocked(self, x, y):
        """(x, y) 是否被堵；越界抛 GridError。"""
        self._check(x, y)
        return (x, y) in self._blocked

    def passable(self, x, y):
        """界内且没被堵才算可通行；越界返回 False，不抛异常。"""
        return self.in_bounds(x, y) and (x, y) not in self._blocked

    def require_cell(self, cell, name="cell"):
        """校验 cell 是界内可通行格，返回规整的 (x, y)；否则抛 GridError。"""
        if not isinstance(cell, (list, tuple)) or len(cell) != 2:
            raise GridError("%s %r is not a (x, y) pair" % (name, cell))
        x, y = cell
        if not isinstance(x, int) or not isinstance(y, int):
            raise GridError("%s %r is not a pair of ints" % (name, cell))
        self._check(x, y)
        if (x, y) in self._blocked:
            raise GridError("%s %r is blocked" % (name, cell))
        return (x, y)

    def set_blocked(self, x, y, flag=True):
        """改 (x, y) 的阻塞状态，返回改动前的状态。"""
        self._check(x, y)
        cell = (x, y)
        was = cell in self._blocked
        if flag:
            self._blocked.add(cell)
        else:
            self._blocked.discard(cell)
        return was

    def blocked_cells(self):
        """全部阻塞格，按坐标升序。"""
        return tuple(sorted(self._blocked))

    def copy(self):
        """独立副本，改副本不影响原图。"""
        clone = Grid(self.width, self.height)
        clone._blocked = set(self._blocked)
        return clone

    # -- 邻居与步长 --------------------------------------------

    def neighbors(self, x, y):
        """(x, y) 的可达邻居，按 DIRECTIONS 顺序给出 (nx, ny, cost)。"""
        self._check(x, y)
        out = []
        for dx, dy in DIRECTIONS:
            nx, ny = x + dx, y + dy
            if not self.in_bounds(nx, ny):
                continue
            if (nx, ny) in self._blocked:
                continue
            if dx != 0 and dy != 0:
                if (x + dx, y) in self._blocked and (x, y + dy) in self._blocked:
                    continue
            out.append((nx, ny, SQRT2 if dx != 0 and dy != 0 else 1.0))
        return tuple(out)

    def step_cost(self, a, b):
        """相邻两格间的步长，斜为 SQRT2，横竖为 1.0；不相邻抛 GridError。"""
        ax, ay = a
        bx, by = b
        self._check(ax, ay)
        self._check(bx, by)
        dx = bx - ax
        dy = by - ay
        if (dx == 0 and dy == 0) or max(abs(dx), abs(dy)) != 1:
            raise GridError("cells %r and %r are not neighbours" % (a, b))
        return SQRT2 if dx != 0 and dy != 0 else 1.0
