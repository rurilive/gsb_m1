"""布隆过滤器，纯标准库。

按目标误判率与预期条目数确定位数组大小和散列个数，散列函数个数取理论
最优值。条目数超过建过滤器时的预期值后自动扩容（倍增预期值、按当前
全部键重建位数组），不让误判率随写入量一路飘高。
"""

import hashlib
import math
import pickle

_FORMAT_MAGIC = b"BLMF"
_FORMAT_VERSION = 1


def _sizing(expected_items, error_rate):
    """给定预期条目数与目标误判率，返回 (位数组长度, 散列个数)。"""
    if expected_items < 1:
        raise ValueError("expected_items must be >= 1")
    if not 0.0 < error_rate < 1.0:
        raise ValueError("error_rate must be in (0, 1)")
    # m = -n ln p / (ln 2)^2；取整后在相邻整数 k 里挑实际误判率更低的，
    # 若取整把估算率顶过了目标，就把位数组补几位直到不超目标。
    minimum_bits = max(8, math.ceil(-expected_items * math.log(error_rate) / math.log(2) ** 2))
    num_bits = minimum_bits
    while True:
        optimal = num_bits / expected_items * math.log(2)

        def rate_for(k):
            return (1.0 - math.exp(-k * expected_items / num_bits)) ** k

        lower = max(1, math.floor(optimal))
        upper = max(1, math.ceil(optimal))
        num_hashes = lower if rate_for(lower) <= rate_for(upper) else upper
        if rate_for(num_hashes) <= error_rate:
            break
        num_bits += 1
    return num_bits, num_hashes


def _digest(value):
    """键归一成 32 字节指纹。str 按 utf-8，bytes 直接用，其余 pickle。"""
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raw = pickle.dumps(value)
    return hashlib.blake2b(raw, digest_size=32).digest()


class BloomFilter:
    """可扩容、可落盘的布隆过滤器，不存在假阴。

    expected_items: 建过滤器时的预期条目数，决定初始容量。
    error_rate: 目标误判率（假阳率），取值 (0, 1)。
    写入条目超过 expected_items 时自动扩容：预期容量倍增并按全部已写键
    重建位数组，把误判率拉回目标值附近。
    """

    def __init__(self, expected_items, error_rate):
        self._expected_items = expected_items
        self._error_rate = error_rate
        num_bits, num_hashes = _sizing(expected_items, error_rate)
        self._num_bits = num_bits
        self._num_hashes = num_hashes
        self._bits = bytearray((num_bits + 7) // 8)
        # 已写键全集：扩容重建与落盘都要靠它
        self._items = set()

    @property
    def expected_items(self):
        return self._expected_items

    @property
    def error_rate(self):
        return self._error_rate

    @property
    def num_bits(self):
        return self._num_bits

    @property
    def num_hashes(self):
        return self._num_hashes

    def __len__(self):
        return len(self._items)

    def add(self, key):
        """写入一个键。超过建过滤器时的容量先扩容。"""
        if key in self._items:
            return
        self._items.add(key)
        if len(self._items) > self._expected_items:
            self._grow()
        self._set_bits(key)

    def might_contain(self, key):
        """键可能在则 True，肯定不在则 False（后者永不出错）。"""
        return all(self._bit_set(index) for index in self._indexes(key))

    def __contains__(self, key):
        return self.might_contain(key)

    def estimated_false_positive_rate(self):
        """按当前条目数估的假阳率：(1 - e^(-kn/m))^k。"""
        if not self._items:
            return 0.0
        exponent = -self._num_hashes * len(self._items) / self._num_bits
        return (1.0 - math.exp(exponent)) ** self._num_hashes

    def rebuild(self, keys, expected_items=None):
        """按给定键集重建位数组。键集变了（如压实合并）必须走这里，
        留着旧位数组会对新并进来的键产生假阴。expected_items 可同步调大。"""
        items = set(keys)
        if expected_items is not None:
            self._expected_items = expected_items
        # 现有容量装不下就继续倍增，直到装得下
        while len(items) > self._expected_items:
            self._expected_items *= 2
        num_bits, num_hashes = _sizing(self._expected_items, self._error_rate)
        self._num_bits = num_bits
        self._num_hashes = num_hashes
        self._bits = bytearray((num_bits + 7) // 8)
        self._items = items
        for key in items:
            self._set_bits(key)

    def dump(self, path):
        """落盘：魔数 + 版本 + pickle 的参数、已写键全集、位数组。"""
        payload = {
            "expected_items": self._expected_items,
            "error_rate": self._error_rate,
            "num_bits": self._num_bits,
            "num_hashes": self._num_hashes,
            "items": self._items,
            "bits": bytes(self._bits),
        }
        with open(path, "wb") as handle:
            handle.write(_FORMAT_MAGIC)
            handle.write(bytes([_FORMAT_VERSION]))
            pickle.dump(payload, handle)

    @classmethod
    def load(cls, path):
        """从落盘文件读回，参数与位数组逐一对账，行为不落盘前后一致。"""
        with open(path, "rb") as handle:
            magic = handle.read(len(_FORMAT_MAGIC))
            if magic != _FORMAT_MAGIC:
                raise ValueError("not a bloom filter file")
            version = handle.read(1)
            if version != bytes([_FORMAT_VERSION]):
                raise ValueError("unsupported bloom filter format version")
            payload = pickle.load(handle)
        flt = cls.__new__(cls)
        expected_items = payload["expected_items"]
        error_rate = payload["error_rate"]
        num_bits, num_hashes = _sizing(expected_items, error_rate)
        if num_bits != payload["num_bits"] or num_hashes != payload["num_hashes"]:
            raise ValueError("bloom filter parameters mismatch")
        flt._expected_items = expected_items
        flt._error_rate = error_rate
        flt._num_bits = num_bits
        flt._num_hashes = num_hashes
        flt._items = set(payload["items"])
        bits = bytearray(payload["bits"])
        if len(bits) != (num_bits + 7) // 8:
            raise ValueError("bloom filter bit array size mismatch")
        flt._bits = bits
        return flt

    def _grow(self):
        """容量倍增并按全部已写键重建位数组。"""
        self._expected_items *= 2
        num_bits, num_hashes = _sizing(self._expected_items, self._error_rate)
        self._num_bits = num_bits
        self._num_hashes = num_hashes
        self._bits = bytearray((num_bits + 7) // 8)
        for existing in self._items:
            self._set_bits(existing)

    def _indexes(self, key):
        # 双散列派生 k 个槽位：h_i = h1 + i*h2 (mod m)
        digest = _digest(key)
        h1 = int.from_bytes(digest[:16], "big")
        h2 = int.from_bytes(digest[16:], "big") or 1
        return [(h1 + step * h2) % self._num_bits for step in range(self._num_hashes)]

    def _set_bits(self, key):
        for index in self._indexes(key):
            self._bits[index >> 3] |= 1 << (index & 7)

    def _bit_set(self, index):
        return (self._bits[index >> 3] >> (index & 7)) & 1
