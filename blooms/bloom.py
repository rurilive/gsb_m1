"""布隆过滤器，纯标准库。

位数组按目标误判率和预估条目数算出，双哈希派生多个探测位。
过滤器不保存键本身，键集合变化时由持有方用 ``rebuild`` 重建；
条目数超出建时容量导致误判率超目标时，同样用 ``rebuild`` 扩容重建。
"""

import hashlib
import math

MAGIC = 0xB100
VERSION = 1


def _encode_key(key):
    """把常见可哈希键编成稳定字节，重启后编法不变。"""
    if isinstance(key, bytes):
        return b"b:" + key
    if isinstance(key, str):
        return b"s:" + key.encode("utf-8")
    if isinstance(key, bool):
        return b"i:" + str(int(key)).encode("ascii")
    if isinstance(key, int):
        return b"i:" + str(key).encode("ascii")
    if isinstance(key, float):
        return b"f:" + repr(key).encode("ascii")
    raise TypeError(f"unsupported bloom key type: {type(key).__name__}")


class BloomFilter:
    """可重建、可序列化的布隆过滤器。

    expected_items: 建时预估条目数，决定位数组长度。
    error_rate: 目标误判率，取值 (0, 1)。
    """

    def __init__(self, expected_items, error_rate=0.01):
        expected_items = int(expected_items)
        if expected_items < 1:
            raise ValueError("expected_items must be >= 1")
        error_rate = float(error_rate)
        if not 0.0 < error_rate < 1.0:
            raise ValueError("error_rate must be in (0, 1)")
        self._expected_items = expected_items
        self._error_rate = error_rate
        self._bits = _optimal_bits(expected_items, error_rate)
        self._hashes = _optimal_hashes(self._bits, expected_items)
        self._count = 0
        self._array = bytearray((self._bits + 7) // 8)

    @property
    def error_rate(self):
        return self._error_rate

    @property
    def expected_items(self):
        """建时（或最近一次重建）预估的条目数。"""
        return self._expected_items

    @property
    def items(self):
        """实际加入的条目数。"""
        return self._count

    @property
    def saturated(self):
        """实际条目数超过容量，误判率已超过建时目标。"""
        return self._count > self._expected_items

    @property
    def estimated_false_positive_rate(self):
        """按当前条目数估的误判率：(1 - e^(-kn/m))^k。"""
        if self._bits == 0:
            return 1.0
        return (1.0 - math.exp(-self._hashes * self._count / self._bits)) ** self._hashes

    @property
    def fpp(self):
        """estimated_false_positive_rate 的短名。"""
        return self.estimated_false_positive_rate

    def add(self, key):
        """加入一个键。"""
        digest = hashlib.sha1(_encode_key(key)).digest()
        first = int.from_bytes(digest[:4], "big")
        second = int.from_bytes(digest[4:8], "big")
        bits = self._bits
        for i in range(self._hashes):
            pos = (first + i * second) % bits
            self._array[pos >> 3] |= 1 << (pos & 7)
        self._count += 1

    def __contains__(self, key):
        digest = hashlib.sha1(_encode_key(key)).digest()
        first = int.from_bytes(digest[:4], "big")
        second = int.from_bytes(digest[4:8], "big")
        bits = self._bits
        for i in range(self._hashes):
            pos = (first + i * second) % bits
            if not (self._array[pos >> 3] >> (pos & 7)) & 1:
                return False
        return True

    def might_contain(self, key):
        """True 表示可能有（有误判），False 表示肯定没有（无假阴）。"""
        return key in self

    def rebuild(self, keys, expected_items=None):
        """用给定键集合重建过滤器，键集变化或扩容时调用。

        不传 expected_items 时容量翻倍，直到容得下全部键，
        保证膨胀后误判率回落到目标附近。
        """
        keys = list(keys)
        capacity = int(expected_items) if expected_items is not None else self._expected_items
        if expected_items is not None and capacity < 1:
            raise ValueError("expected_items must be >= 1")
        while capacity < len(keys):
            capacity *= 2
        self._expected_items = capacity
        self._bits = _optimal_bits(capacity, self._error_rate)
        self._hashes = _optimal_hashes(self._bits, capacity)
        self._count = 0
        self._array = bytearray((self._bits + 7) // 8)
        for key in keys:
            self.add(key)

    def to_dict(self):
        """序列化成纯 JSON 值的 dict。"""
        return {
            "magic": MAGIC,
            "version": VERSION,
            "expected_items": self._expected_items,
            "error_rate": self._error_rate,
            "bits": self._bits,
            "hashes": self._hashes,
            "count": self._count,
            "data": self._array.hex(),
        }

    @classmethod
    def from_dict(cls, obj):
        """to_dict 的逆操作，参数对不上直接报错，不做静默将就。"""
        if not isinstance(obj, dict) or obj.get("magic") != MAGIC or obj.get("version") != VERSION:
            raise ValueError("invalid bloom filter image")
        expected_items = int(obj["expected_items"])
        error_rate = float(obj["error_rate"])
        bits = int(obj["bits"])
        hashes = int(obj["hashes"])
        count = int(obj["count"])
        if expected_items < 1 or not 0.0 < error_rate < 1.0:
            raise ValueError("invalid bloom filter image")
        if bits != _optimal_bits(expected_items, error_rate):
            raise ValueError("bloom filter image does not match parameters")
        if hashes != _optimal_hashes(bits, expected_items):
            raise ValueError("bloom filter image does not match parameters")
        data = bytes.fromhex(obj["data"])
        need = (bits + 7) // 8
        if len(data) != need or count < 0:
            raise ValueError("invalid bloom filter image")
        restored = cls.__new__(cls)
        restored._expected_items = expected_items
        restored._error_rate = error_rate
        restored._bits = bits
        restored._hashes = hashes
        restored._count = count
        restored._array = bytearray(data)
        return restored


def _optimal_bits(expected_items, error_rate):
    return max(1, int(math.ceil(-expected_items * math.log(error_rate) / (math.log(2) ** 2))))


def _optimal_hashes(bits, expected_items):
    return max(1, int(round(bits / expected_items * math.log(2))))
