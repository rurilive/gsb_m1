"""容量档位划分。

请求容量向上取整到最近的档位；超过最大档位的请求没有归属档位，
tier_of 返回 None，统计上记作 oversize。
"""

from bufpool.errors import InvalidSize

TIERS = (256, 1024, 4096, 16384, 65536)

OVERSIZE = "oversize"


def check_size(size):
    """校验请求容量，合法则原样返回。"""
    if isinstance(size, bool) or not isinstance(size, int):
        raise InvalidSize("容量必须是整数，收到 %r" % (size,))
    if size <= 0:
        raise InvalidSize("容量必须为正数，收到 %r" % (size,))
    return size


def tier_of(size):
    """能装下 size 的最小档位；超过最大档位时返回 None。"""
    check_size(size)
    for tier in TIERS:
        if size <= tier:
            return tier
    return None


def tier_key(size):
    """统计口径用的档位标签：档位值，或超出最大档位时的 oversize。"""
    tier = tier_of(size)
    return tier if tier is not None else OVERSIZE
