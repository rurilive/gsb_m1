"""IPv4 地址的整数表示与文本形式互转。

地址一律用 32 位无符号整数表示（大端解释），0.0.0.0 是 0，
255.255.255.255 是 4294967295。文本形式就是常见的点分四段，
加前缀长度写成 a.b.c.d/len。
"""

ADDR_BITS = 32
ADDR_MAX = (1 << ADDR_BITS) - 1


def parse_addr(text):
    """点分四段文本转整数。

    每段必须是十进制数字、取值 0 到 255，且不许有前导零
    （单独的 0 除外，010 这种写法报 ValueError）。
    """
    if not isinstance(text, str):
        raise TypeError("address must be a string, got %s" % type(text).__name__)
    parts = text.split(".")
    if len(parts) != 4:
        raise ValueError("expected four octets: %r" % text)
    value = 0
    for part in parts:
        if not part.isdigit():
            raise ValueError("bad octet in %r" % text)
        if len(part) > 1 and part.startswith("0"):
            raise ValueError("leading zero in %r" % text)
        octet = int(part)
        if octet > 255:
            raise ValueError("octet out of range in %r" % text)
        value = (value << 8) | octet
    return value


def format_addr(value):
    """整数转点分四段文本，越界报 ValueError。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("address must be an int, got %s" % type(value).__name__)
    if not 0 <= value <= ADDR_MAX:
        raise ValueError("address out of range: %d" % value)
    return "%d.%d.%d.%d" % (
        (value >> 24) & 255,
        (value >> 16) & 255,
        (value >> 8) & 255,
        value & 255,
    )


def check_prefix(prefix):
    """前缀长度必须是 0 到 32 的整数。"""
    if isinstance(prefix, bool) or not isinstance(prefix, int):
        raise TypeError("prefix must be an int, got %s" % type(prefix).__name__)
    if not 0 <= prefix <= ADDR_BITS:
        raise ValueError("prefix out of range: %d" % prefix)
    return prefix


def block_size(prefix):
    """前缀长度对应网段的地址个数，2 的 (32 - prefix) 次方。"""
    return 1 << (ADDR_BITS - check_prefix(prefix))


def network_of(addr, prefix):
    """addr 所在网段的网络地址，主机位清零。"""
    return addr & ~(block_size(prefix) - 1)


def broadcast_of(addr, prefix):
    """addr 所在网段的广播地址。"""
    return network_of(addr, prefix) | (block_size(prefix) - 1)


def format_cidr(network, prefix):
    """(网络地址, 前缀长度) 转成 a.b.c.d/len 文本。"""
    return "%s/%d" % (format_addr(network_of(network, prefix)), check_prefix(prefix))


def parse_cidr(text):
    """解析 a.b.c.d/len，返回 (网络地址, 前缀长度)，主机位归零。"""
    if not isinstance(text, str):
        raise TypeError("cidr must be a string, got %s" % type(text).__name__)
    addr_text, sep, prefix_text = text.partition("/")
    if not sep:
        raise ValueError("missing /len in %r" % text)
    if not prefix_text.isdigit():
        raise ValueError("bad prefix in %r" % text)
    prefix = check_prefix(int(prefix_text))
    return network_of(parse_addr(addr_text), prefix), prefix


def usable_bounds(network, prefix):
    """网段里可分配给主机的首尾地址。

    /30 及更短按惯例扣掉网络地址与广播地址；点到点链路常用的
    /31 两个地址都能用，/32 的主机位单个地址也能用。
    """
    last = broadcast_of(network, prefix)
    if prefix >= 31:
        return network, last
    return network + 1, last - 1
