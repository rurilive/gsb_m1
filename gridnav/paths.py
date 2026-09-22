"""路径校验与代价计算。"""

from gridnav.grid import GridError


class PathError(ValueError):
    """路径非法：空路径、跳格、穿过障碍或斜穿墙角。"""


def validate_path(grid, path):
    """校验一条路径；有问题抛 PathError，正常返回 None。

    路径是 (x, y) 的序列，首尾包含起终点；每格必须可通行，相邻两格必须
    一步可达（沿用 grid.neighbors 的规则，含斜穿墙角限制）。
    """
    if not isinstance(path, (list, tuple)):
        raise PathError("path must be a list or tuple")
    if not path:
        raise PathError("path is empty")
    for cell in path:
        if not isinstance(cell, (list, tuple)) or len(cell) != 2:
            raise PathError("cell %r is not a (x, y) pair" % (cell,))
        x, y = cell
        if not isinstance(x, int) or not isinstance(y, int):
            raise PathError("cell %r is not a pair of ints" % (cell,))
        if not grid.in_bounds(x, y):
            raise PathError("cell %r out of bounds" % (cell,))
        if not grid.passable(x, y):
            raise PathError("cell %r is blocked" % (cell,))
    for a, b in zip(path, path[1:]):
        reachable = {(nx, ny) for nx, ny, _cost in grid.neighbors(a[0], a[1])}
        if (b[0], b[1]) not in reachable:
            raise PathError("no legal step from %r to %r" % (tuple(a), tuple(b)))


def path_cost(grid, path):
    """路径总代价：横竖步 1.0、斜步 SQRT2，逐段累加。"""
    validate_path(grid, path)
    total = 0.0
    for a, b in zip(path, path[1:]):
        total += grid.step_cost(a, b)
    return total
