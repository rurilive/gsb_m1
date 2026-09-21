"""字节级 LZ77 压缩核，自己实现，只用标准库。

压缩流是一串 token，每种都以一个标记字节开头：

- 0x00 字面段：varint 长度 + 原始字节
- 0x01 命中段：varint 偏移 + varint 长度；从当前位置往前数 offset 个
  字节处复制 length 个字节，允许与目标区间重叠

offset 可以指到 preset 里去：解压时把 preset 接在数据前面一起当历史，
解完再把这截前缀摘掉。compress 与 decompress 的 preset 必须一致，不
一致时解出来的数据不可信，交给上层的校验和兜底。

varint 是小端 base-128（每字节低 7 位有效，最高位表示续读）。
"""

from .errors import FormatError

#: 小于这个长度的匹配不划算，直接走字面量。
MIN_MATCH = 4

#: 单次命中最多复制这么多字节。
MAX_MATCH = 4096

#: 每个位置最多比这么多条候选链，控制压缩耗时。
MAX_CHAIN = 64

#: 匹配能往回看的最远距离，preset 加数据一起算在内。
MAX_DIST = 65536

#: 同一个片段在 preset 里最多挑几个位置当候选。
MAX_PRESET_HITS = 8


def encode_varint(value):
    """把非负整数编成 varint 字节串。"""
    if value < 0:
        raise ValueError("varint 不支持负数")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def decode_varint(buf, pos):
    """从 pos 处读一个 varint，返回 (值, 读完后的下标)。"""
    value = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise FormatError("varint 读到一半就没了")
        byte = buf[pos]
        pos += 1
        if byte & 0x80:
            value |= (byte & 0x7F) << shift
            shift += 7
            if shift > 28:
                raise FormatError("varint 超过 5 字节，不像是本格式")
        else:
            value |= byte << shift
            return value, pos


def _preset_positions(preset, key):
    """在 preset 里找 key 出现的所有位置，只留最后 MAX_PRESET_HITS 个。"""
    hits = []
    start = preset.find(key)
    while start >= 0:
        hits.append(start)
        start = preset.find(key, start + 1)
    return hits[-MAX_PRESET_HITS:]


def compress(data, preset=b""):
    """把 data 压成 token 流；preset 是允许被命中的前置历史。"""
    data = bytes(data)
    preset = bytes(preset)
    if not data:
        return b""
    buf = preset + data
    base = len(preset)
    size = len(data)
    out = bytearray()
    head = {}
    prev = [-1] * len(buf)
    # preset 里的候选位置按需查，查过的片段记下来，别每条消息重扫一遍。
    hits_cache = {}
    pos = 0
    lit = 0
    while pos < size:
        here = base + pos
        key = None
        if pos + MIN_MATCH <= size:
            key = buf[here:here + MIN_MATCH]
        best_len = 0
        best_off = 0
        if key is not None:
            cap = size - pos
            if cap > MAX_MATCH:
                cap = MAX_MATCH
            cand = head.get(key, -1)
            tried = 0
            while cand >= 0 and tried < MAX_CHAIN and here - cand <= MAX_DIST:
                match = 0
                while match < cap and buf[cand + match] == buf[here + match]:
                    match += 1
                if match > best_len:
                    best_len = match
                    best_off = here - cand
                    if match == cap:
                        break
                cand = prev[cand]
                tried += 1
            if preset and best_len < cap:
                hits = hits_cache.get(key)
                if hits is None:
                    hits = _preset_positions(preset, key)
                    hits_cache[key] = hits
                for start in hits:
                    match = 0
                    while match < cap and buf[start + match] == buf[here + match]:
                        match += 1
                    if match > best_len:
                        best_len = match
                        best_off = here - start
                        if match == cap:
                            break
        if best_len >= MIN_MATCH:
            if pos > lit:
                out.append(0x00)
                out += encode_varint(pos - lit)
                out += data[lit:pos]
            out.append(0x01)
            out += encode_varint(best_off)
            out += encode_varint(best_len)
            end = pos + best_len
            while pos < end:
                here = base + pos
                if pos + MIN_MATCH <= size:
                    key = buf[here:here + MIN_MATCH]
                    prev[here] = head.get(key, -1)
                    head[key] = here
                pos += 1
            lit = pos
        else:
            if key is not None:
                prev[here] = head.get(key, -1)
                head[key] = here
            pos += 1
    if lit < size:
        out.append(0x00)
        out += encode_varint(size - lit)
        out += data[lit:]
    return bytes(out)


def decompress(blob, preset=b"", max_size=None):
    """把 token 流解回字节；preset 必须与压缩时一致。

    max_size 给了解压结果（不含 preset）的长度上限，超了直接抛
    FormatError，防止畸形流把内存撑爆。
    """
    blob = bytes(blob)
    preset = bytes(preset)
    out = bytearray(preset)
    base = len(preset)
    limit = None if max_size is None else base + max_size
    pos = 0
    end = len(blob)
    while pos < end:
        tag = blob[pos]
        pos += 1
        if tag == 0x00:
            length, pos = decode_varint(blob, pos)
            if pos + length > end:
                raise FormatError("字面段长度 %d 超出流尾" % length)
            out += blob[pos:pos + length]
            pos += length
        elif tag == 0x01:
            offset, pos = decode_varint(blob, pos)
            length, pos = decode_varint(blob, pos)
            if offset < 1 or offset > len(out):
                raise FormatError("命中段偏移 %d 指到历史之外" % offset)
            if length < 1:
                raise FormatError("命中段长度为 0")
            if limit is not None and len(out) + length > limit:
                raise FormatError("解压结果超出 max_size")
            if length <= offset:
                start = len(out) - offset
                out += out[start:start + length]
            else:
                start = len(out) - offset
                while length:
                    out.append(out[start])
                    start += 1
                    length -= 1
        else:
            raise FormatError("未知 token 标记 0x%02x" % tag)
    return bytes(out[base:])
