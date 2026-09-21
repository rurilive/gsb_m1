"""固定边长的经纬格网切分。

格边长按 1 度除以整数来取，行号自南向北从 -90 度起编，列号自西向东
从 -180 度起编；经度先归一化，所以列号总落在 [0, 360 * per_degree) 里。
"""

import math

from .geo import normalize_lon

DEFAULT_CELL_DEG = 0.05


def check_cell_deg(cell_deg):
    """校验格边长：正数，且 1 度能切成整数格。返回浮点边长。"""
    if isinstance(cell_deg, bool) or not isinstance(cell_deg, (int, float)):
        raise ValueError("格边长必须是数字，收到 %r" % (cell_deg,))
    value = float(cell_deg)
    if not math.isfinite(value) or value <= 0.0 or value > 90.0:
        raise ValueError("格边长必须落在 (0, 90] 里，收到 %r" % (cell_deg,))
    if abs(round(1.0 / value) - 1.0 / value) > 1e-9:
        raise ValueError("格边长要能整除 1 度，收到 %r" % (cell_deg,))
    return value


def per_degree(cell_deg=None):
    """每 1 度切出的格数。"""
    if cell_deg is None:
        cell_deg = DEFAULT_CELL_DEG
    return int(round(1.0 / check_cell_deg(cell_deg)))


def cell_row(lat, cell_deg=None):
    """纬度所在行号。"""
    return int(math.floor((float(lat) + 90.0) * per_degree(cell_deg)))


def cell_col(lon, cell_deg=None):
    """归一化经度所在列号。"""
    return int(math.floor((normalize_lon(lon) + 180.0) * per_degree(cell_deg)))


def cell_of(lat, lon, cell_deg=None):
    """点所在格，返回 (row, col)。"""
    return (cell_row(lat, cell_deg), cell_col(lon, cell_deg))
