"""MessageCodec：一条消息压成一个自包含的帧。

每条消息单独走一遍压缩核，互相之间不共享任何上下文。压完比原文还
大的话就退回原文直存，帧头一样，收端不用分两套逻辑。
"""

from . import frame as frame_mod
from . import lz
from .errors import FormatError


class MessageCodec:
    """逐条独立压缩短消息，编码统计挂在实例上。"""

    def __init__(self):
        self._messages = 0
        self._raw_bytes = 0
        self._encoded_bytes = 0
        self._decoded = 0

    def encode(self, data):
        """把 bytes 编成一个帧。"""
        data = bytes(data)
        blob = lz.compress(data)
        if len(blob) < len(data):
            kind, payload = frame_mod.KIND_LZ, blob
        else:
            kind, payload = frame_mod.KIND_RAW, data
        packed = frame_mod.pack_frame(
            kind, len(data), payload, frame_mod.fnv32(data)
        )
        self._messages += 1
        self._raw_bytes += len(data)
        self._encoded_bytes += len(packed)
        return packed

    def decode(self, frame):
        """把帧解回原文；结构不对、校验不过一律抛 FormatError。"""
        kind, raw_len, payload, checksum = frame_mod.unpack_frame(frame)
        if kind == frame_mod.KIND_RAW:
            data = payload
        else:
            data = lz.decompress(payload, max_size=raw_len)
        if len(data) != raw_len:
            raise FormatError(
                "解出 %d 字节，帧头写的是 %d 字节" % (len(data), raw_len)
            )
        if frame_mod.fnv32(data) != checksum:
            raise FormatError("校验和对不上，帧坏了或原文被换过")
        self._decoded += 1
        return data

    def stats(self):
        """累计统计快照，ratio 是编码后总字节除以原文总字节。"""
        ratio = self._encoded_bytes / self._raw_bytes if self._raw_bytes else 0.0
        return {
            "messages": self._messages,
            "raw_bytes": self._raw_bytes,
            "encoded_bytes": self._encoded_bytes,
            "decoded": self._decoded,
            "ratio": ratio,
        }
