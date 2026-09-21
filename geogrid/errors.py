"""geogrid 的异常类型。"""


class GeoError(Exception):
    """geogrid 异常的基类。"""


class InvalidCoordinate(GeoError):
    """经纬度或参数不合法。"""


class DuplicateId(GeoError):
    """同一个 id 被登记两次。"""


class UnknownId(GeoError):
    """操作了一个索引里不存在的 id。"""
