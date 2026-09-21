"""预共享字典：训练、版本管理与带字典的编解码。

短消息逐条独立压缩时字典积累不起来，这里把语料里的高频片段提前训
成一段字典，收发双方预共享。压缩时拿它当 preset 历史（见 lz.py），
帧头带上字典版本，收端按版本取同一份字典还原；没字典的老 MZ1 帧
照解。

MZ2 帧布局：

    b"MZ2"     3 字节魔数
    种类       1 字节：0 原文直存，1 LZ 压缩体（含义同 MZ1）
    字典版本   varint，0 表示没字典
    raw_len    varint，原文长度
    payload    压缩体或原文
    校验和     4 字节大端，原文的 FNV-1a 32 位
"""

import os
import time

from . import frame as frame_mod
from . import lz
from .codec import MessageCodec
from .errors import DictVersionError, FormatError

#: 带字典版本的帧魔数。
MAGIC2 = b"MZ2"

#: 帧头里这个版本号表示“没字典”。
VERSION_NONE = 0

#: 训练时统计的高频窗口长度。
_GRAM = 8

#: 一个窗口至少出现这么多次才进候选。
_MIN_COUNT = 3

#: 命中段的编码开销大约三个字节，算收益时扣掉。
_TOKEN_COST = 3

#: 字典文件的命名模板。
_FILE_TEMPLATE = "dict_v%06d.bin"


def train_dictionary(samples, max_size):
    """从语料训一段不超过 max_size 的字典。

    先数所有 _GRAM 字节窗口的出现次数，再把高频窗口按重叠关系首尾
    接成长片段，按估计收益从高到低往字典里装，装满为止。语料为空
    或 max_size 太小就返回空串。
    """
    samples = [bytes(s) for s in samples]
    if max_size < _GRAM or not samples:
        return b""
    counts = {}
    for msg in samples:
        for i in range(len(msg) - _GRAM + 1):
            key = msg[i:i + _GRAM]
            counts[key] = counts.get(key, 0) + 1
    grams = [(count, gram) for gram, count in counts.items() if count >= _MIN_COUNT]
    if not grams:
        return b""
    grams.sort(reverse=True)
    # 前 7 字节 -> 窗口、后 7 字节 -> 窗口，用来把重叠窗口接成长片段；
    # setdefault 留下次数最高的那个接法。
    by_prefix = {}
    by_suffix = {}
    for count, gram in grams:
        by_prefix.setdefault(gram[:_GRAM - 1], gram)
        by_suffix.setdefault(gram[1:], gram)
    consumed = set()
    fragments = []
    for count, gram in grams:
        if gram in consumed:
            continue
        frag = bytearray(gram)
        consumed.add(gram)
        cur = gram
        while True:
            nxt = by_prefix.get(cur[1:])
            if nxt is None or nxt in consumed:
                break
            frag.append(nxt[-1])
            consumed.add(nxt)
            cur = nxt
        cur = gram
        while True:
            prv = by_suffix.get(cur[:_GRAM - 1])
            if prv is None or prv in consumed:
                break
            frag[:0] = prv[:1]
            consumed.add(prv)
            cur = prv
        fragments.append((count * (len(frag) - _TOKEN_COST), bytes(frag)))
    fragments.sort(reverse=True)
    out = bytearray()
    for score, frag in fragments:
        if score <= 0:
            break
        if len(frag) > max_size - len(out):
            continue
        if frag in out:
            continue
        out += frag
    return bytes(out)


class DictStore:
    """管一目录的字典版本，编解码走带版本号的 MZ2 帧。

    rollout(samples) 训一版新字典并在 samples 上实测编码总量，比现役
    方案省的比例达到 min_gain 才上线，否则丢弃；多版本共存，超过
    max_versions 时淘汰最老的版本。
    """

    def __init__(self, directory, max_versions=4, min_gain=0.05, dict_max_size=4096):
        if max_versions < 1:
            raise ValueError("max_versions 至少为 1")
        self._dir = os.fspath(directory)
        os.makedirs(self._dir, exist_ok=True)
        self._max_versions = max_versions
        self._min_gain = float(min_gain)
        self._dict_max_size = dict_max_size
        self._versions = {}
        for name in sorted(os.listdir(self._dir)):
            version = self._file_version(name)
            if version is None:
                continue
            with open(os.path.join(self._dir, name), "rb") as fh:
                self._versions[version] = fh.read()
        self._active = max(self._versions) if self._versions else VERSION_NONE
        self._next = self._active + 1
        self._evict()
        self._mz1 = MessageCodec()

    @staticmethod
    def _file_version(name):
        if name.startswith("dict_v") and name.endswith(".bin"):
            try:
                return int(name[len("dict_v"):-len(".bin")])
            except ValueError:
                return None
        return None

    @property
    def active_version(self):
        """当前在线的字典版本，0 表示还没字典。"""
        return self._active

    def versions(self):
        """手里现存的所有字典版本，升序。"""
        return tuple(sorted(self._versions))

    def dictionary(self, version=None):
        """取某个版本的字典；没有或已淘汰就抛 DictVersionError。"""
        if version is None:
            version = self._active
        if version == VERSION_NONE:
            return b""
        try:
            return self._versions[version]
        except KeyError:
            raise DictVersionError(version)

    def rollout(self, samples):
        """训一版新字典并实测，够好才上线；返回一份中文报告 dict。

        报告里 deployed 写明上线与否，baseline_ratio / candidate_ratio
        是上线前后两种方案在同一批样本上的实测编码总量比率。
        """
        samples = [bytes(s) for s in samples]
        started = time.perf_counter()
        dictionary = train_dictionary(samples, self._dict_max_size)
        trained = time.perf_counter()
        raw = sum(len(s) for s in samples)
        baseline = sum(
            len(self._encode_with(s, self._active, self.dictionary()))
            for s in samples
        )
        candidate = sum(
            len(self._encode_with(s, self._next, dictionary)) for s in samples
        )
        gain = (baseline - candidate) / baseline if baseline else 0.0
        deployed = bool(dictionary) and gain >= self._min_gain
        report = {
            "deployed": deployed,
            "version": None,
            "active_version": self._active,
            "dict_size": len(dictionary),
            "samples": len(samples),
            "raw_bytes": raw,
            "baseline_ratio": baseline / raw if raw else 0.0,
            "candidate_ratio": candidate / raw if raw else 0.0,
            "gain": gain,
            "min_gain": self._min_gain,
            "train_seconds": trained - started,
            "total_seconds": time.perf_counter() - started,
        }
        if deployed:
            version = self._next
            self._next += 1
            self._versions[version] = dictionary
            self._active = version
            self._write_file(version, dictionary)
            self._evict()
            report["version"] = version
            report["active_version"] = version
            report["reason"] = "增益 %.3f 达到阈值 %.3f，已上线为 v%d" % (
                gain, self._min_gain, version)
        else:
            report["reason"] = "增益 %.3f 不到阈值 %.3f，维持现状" % (
                gain, self._min_gain)
        return report

    @staticmethod
    def _encode_with(data, version, dictionary):
        blob = lz.compress(data, preset=dictionary)
        if len(blob) < len(data):
            kind, payload = frame_mod.KIND_LZ, blob
        else:
            kind, payload = frame_mod.KIND_RAW, data
        head = (
            MAGIC2
            + bytes([kind])
            + lz.encode_varint(version)
            + lz.encode_varint(len(data))
        )
        return head + payload + frame_mod.fnv32(data).to_bytes(4, "big")

    def encode(self, data):
        """用现役字典把 bytes 编成一个 MZ2 帧。"""
        return self._encode_with(bytes(data), self._active, self.dictionary())

    def decode(self, frame):
        """把帧解回原文。

        MZ1 老帧按无字典解；MZ2 帧按帧头版本取字典，版本没训过或已
        淘汰当场抛 DictVersionError；结构不对、校验不过抛 FormatError。
        """
        frame = bytes(frame)
        if frame.startswith(frame_mod.MAGIC):
            return self._mz1.decode(frame)
        if not frame.startswith(MAGIC2):
            raise FormatError("魔数不匹配，不是 msglz 帧")
        if len(frame) < len(MAGIC2) + 1 + 1 + 1 + 4:
            raise FormatError("帧只有 %d 字节，短得不像话" % len(frame))
        kind = frame[len(MAGIC2)]
        if kind not in (frame_mod.KIND_RAW, frame_mod.KIND_LZ):
            raise FormatError("未知帧种类 %d" % kind)
        version, pos = lz.decode_varint(frame, len(MAGIC2) + 1)
        raw_len, pos = lz.decode_varint(frame, pos)
        tail = len(frame) - 4
        if pos > tail:
            raise FormatError("帧在头部就断了")
        payload = frame[pos:tail]
        checksum = int.from_bytes(frame[tail:], "big")
        dictionary = self.dictionary(version)
        if kind == frame_mod.KIND_RAW:
            data = payload
        else:
            data = lz.decompress(payload, preset=dictionary, max_size=raw_len)
        if len(data) != raw_len:
            raise FormatError(
                "解出 %d 字节，帧头写的是 %d 字节" % (len(data), raw_len)
            )
        if frame_mod.fnv32(data) != checksum:
            raise FormatError("校验和对不上，帧坏了或原文被换过")
        return data

    def _write_file(self, version, dictionary):
        path = os.path.join(self._dir, _FILE_TEMPLATE % version)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(dictionary)
        os.replace(tmp, path)

    def _evict(self):
        while len(self._versions) > self._max_versions:
            oldest = min(self._versions)
            if oldest == self._active:
                break
            del self._versions[oldest]
            try:
                os.remove(os.path.join(self._dir, _FILE_TEMPLATE % oldest))
            except OSError:
                pass
