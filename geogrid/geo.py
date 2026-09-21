"""坐标校验、经度归一与球面距离。

经度在入口统一折回 [-180, 180)，所以 180 与 -180 是同一处；
纬度按 [-90, 90] 原样保留。距离用 haversine 公式，地球取球体近似。
"""

import math

from .errors import InvalidCoordinate

EARTH_RADIUS_M = 6371008.8


def check_lat(lat):
    """校验并返回浮点纬度。"""
    if isinstance(lat, bool) or not isinstance(lat, (int, float)):
        raise InvalidCoordinate("纬度必须是数字，收到 %r" % (lat,))
    value = float(lat)
    if not math.isfinite(value) or value < -90.0 or value > 90.0:
        raise InvalidCoordinate("纬度必须在 -90 到 90 之间，收到 %r" % (lat,))
    return value


def check_lon(lon):
    """校验并返回浮点经度；任意有限值都收，归一到别处做。"""
    if isinstance(lon, bool) or not isinstance(lon, (int, float)):
        raise InvalidCoordinate("经度必须是数字，收到 %r" % (lon,))
    value = float(lon)
    if not math.isfinite(value):
        raise InvalidCoordinate("经度必须是有限数，收到 %r" % (lon,))
    return value


def normalize_lon(lon):
    """把经度折回 [-180, 180)，180 落在 -180 上。"""
    return (float(lon) + 180.0) % 360.0 - 180.0


def haversine_m(lat1, lon1, lat2, lon2):
    """两点间的大圆距离，单位米。"""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = phi2 - phi1
    dlam = math.radians(normalize_lon(lon2 - lon1))
    harm = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(harm)))
