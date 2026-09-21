"""预共享字典：从语料里训高频片段，并按版本管起来。

训练（train_dictionary）走多定长 n-gram 计数：在几档片段长度上统计
每个片段在多少条样本里出现（同一条样本里重复出现只计一次，免得一条
长样本霸榜），从长到短挑高频种子，再顺着所有出现位置向右贪心延长
（下一字节在足够多的位置上一致才延），最后在 max_size 预算内贪心装
字典。片段按价值排序，最强的放字典末尾——压缩核以字典为 preset，
末尾离数据近，命中偏移的 varint 更短。

DictStore 把训好的字典落盘成不可变版本（dict-NNNNNN.bin +
versions.json），多版本共存、超量淘汰最老；rollout(samples) 训新
字典并拿真实帧长实测，只有比现役（没有现役时比无字典）好出
min_gain 才上线，不然原样退回。
"""

import json
import pathlib
import threading
import time

from . import frame as frame_mod
from . import lz
from .errors import DictVersionError, FormatError

#: 种子片段最短长度（与压缩核的 MIN_MATCH 对齐，再短省不出 token 钱）。
MIN_FRAGMENT = 6

#: 逐档统计的种子长度，从长到短挑（长片段性价比高）。
SEED_LENGTHS = (16, 12, 10, 8, 6)

#: 片段向右延长的长度上限。
MAX_EXTEND = 64

#: 同一条样本里同一个片段最多跟踪多少个出现位置。
PER_SAMPLE_CAP = 8

#: 延长时下一字节至少要在多大比例的出现位置上一致。
EXTEND_RATIO = 0.8

#: 每个长度档最多延长多少个候选，给训练耗时兜底。
TOP_PER_LENGTH = 200

#: 一次命中相比字面量大约省下的 token 开销（tag + 偏移/长度 varint）。
MATCH_OVERHEAD = 3

#: DictStore 默认的字典体积上限（字节）。
DEFAULT_DICT_SIZE = 4096

#: 默认保留多少个字典版本。
DEFAULT_MAX_VERSIONS = 4

#: 默认要求新字典比现役好出多少（编码比率的绝对差）才上线。
DEFAULT_MIN_GAIN = 0.05


def _count_ngrams(samples, length):
    """统计定长片段在多少条样本里出现；同一条样本里重复出现只计一次。"""
    counts = {}
    for sample in samples:
        if len(sample) < length:
            continue
        seen = set()
        for start in range(len(sample) - length + 1):
            key = sample[start:start + length]
            if key not in seen:
                seen.add(key)
                counts[key] = counts.get(key, 0) + 1
    return counts


def _sample_starts(sample, fragment, cap):
    """fragment 在一条样本里的前 cap 个出现位置。"""
    starts = []
    start = sample.find(fragment)
    while start >= 0:
        starts.append(start)
        if len(starts) >= cap:
            break
        start = sample.find(fragment, start + 1)
    return starts


def _extend_right(samples, fragment, cap=PER_SAMPLE_CAP):
    """顺着 fragment 的出现位置向右延长，返回 (最长片段, 出现位置数)。

    每条样本只跟前 cap 个位置，防止超长样本拖慢训练。每一轮下一字节
    必须在至少 EXTEND_RATIO 的位置上相同（同一样本投出的不同字节各
    计一票），否则说明值开始发散，停在这。
    """
    located = {}
    total = 0
    for index, sample in enumerate(samples):
        starts = _sample_starts(sample, fragment, cap)
        if starts:
            located[index] = starts
            total += len(starts)
    while len(fragment) < MAX_EXTEND and total:
        votes = {}
        next_pos = len(fragment)
        for index, starts in located.items():
            sample = samples[index]
            chosen = set()
            for start in starts:
                pos = start + next_pos
                if pos < len(sample):
                    byte = sample[pos]
                    if byte not in chosen:
                        chosen.add(byte)
                        votes[byte] = votes.get(byte, 0) + 1
        if not votes:
            break
        byte, support = max(votes.items(), key=lambda item: (item[1], -item[0]))
        if support < total * EXTEND_RATIO:
            break
        next_located = {}
        next_total = 0
        for index, starts in located.items():
            sample = samples[index]
            kept = [start for start in starts
                    if start + next_pos < len(sample)
                    and sample[start + next_pos] == byte]
            if kept:
                next_located[index] = kept
                next_total += len(kept)
        located = next_located
        total = next_total
        fragment += bytes([byte])
    return fragment, total


def train_dictionary(samples, max_size):
    """从语料训一本高频片段字典，总长不超过 max_size 字节。

    samples 是 bytes 的可迭代对象；样本太短或预算太小就返回 b""。
    """
    if max_size < 0:
        raise ValueError("max_size 不能为负")
    samples = [bytes(sample) for sample in samples
               if len(sample) >= MIN_FRAGMENT]
    if not samples or max_size < MIN_FRAGMENT:
        return b""
    # 出现门槛随语料规模放宽：小语料 3 次就算数，大语料提高门槛，
    # 省掉延长一堆低频候选的功夫。
    threshold = max(3, len(samples) // 300)
    # 全长度档先收集候选，再全局排序装预算：不然最长档会把短而每条
    # 都命中的结构片段（日期头、字段名）的预算抢走。
    pool = {}
    covered = set()
    for length in SEED_LENGTHS:
        counts = _count_ngrams(samples, length)
        candidates = [item for item in counts.items()
                      if item[1] >= threshold]
        candidates.sort(
            key=lambda item: item[1] * (len(item[0]) - MATCH_OVERHEAD),
            reverse=True)
        for fragment, _seed_count in candidates[:TOP_PER_LENGTH]:
            if any(fragment in old or old in fragment for old in covered):
                continue
            fragment, count = _extend_right(samples, fragment)
            if count < threshold:
                continue
            if any(fragment in old or old in fragment for old in covered):
                continue
            covered.add(fragment)
            previous = pool.get(fragment)
            if previous is None or count > previous:
                pool[fragment] = count
    ranked = sorted(
        ((fragment, count) for fragment, count in pool.items()),
        key=lambda item: item[1] * (len(item[0]) - MATCH_OVERHEAD),
        reverse=True)
    chosen = []
    budget = max_size
    packed = set()
    for fragment, count in ranked:
        if len(fragment) > budget:
            continue
        if any(fragment in old or old in fragment for old in packed):
            continue
        chosen.append((fragment, count))
        packed.add(fragment)
        budget -= len(fragment)
        if budget < MIN_FRAGMENT:
            break
    # 最强的片段放字典末尾，命中偏移更小。
    fragments = [fragment for fragment, _count in reversed(chosen)]
    return b"".join(fragments)


def _build_plain_frame(data):
    """无字典路径：与 MessageCodec.encode 完全相同的选帧逻辑与字节。"""
    blob = lz.compress(data)
    if len(blob) < len(data):
        kind, payload = frame_mod.KIND_LZ, blob
    else:
        kind, payload = frame_mod.KIND_RAW, data
    return frame_mod.pack_frame(
        kind, len(data), payload, frame_mod.fnv32(data))


def _build_dict_frame(data, dictionary, version):
    """带字典路径；字典不划算就退回无字典帧。"""
    blob = lz.compress(data, preset=dictionary)
    version_head = lz.encode_varint(version)
    if len(version_head) + len(blob) < len(data):
        return frame_mod.pack_frame(
            frame_mod.KIND_LZ_DICT, len(data), version_head + blob,
            frame_mod.fnv32(data))
    return _build_plain_frame(data)


class DictStore:
    """磁盘上的多版本字典仓库，兼做带字典的编解码器。

    目录布局::

        <dir>/versions.json        清单：版本序列、现役版本、轮次计数
        <dir>/dict-000001.bin      每个上线版本一份不可变字典

    每次 rollout 都消耗一个版本号（不达标也一样，版本号即训练轮次），
    但只有上线的字典才落盘。编码时没有现役字典就发无字典帧，因此仓库
    刚建好也能直接用；收到无字典老帧（种类 0/1）也照常能解。
    """

    def __init__(self, directory, max_versions=DEFAULT_MAX_VERSIONS,
                 min_gain=DEFAULT_MIN_GAIN, max_size=DEFAULT_DICT_SIZE):
        if max_versions < 1:
            raise ValueError("max_versions 至少为 1")
        self.directory = pathlib.Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_versions = max_versions
        self.min_gain = min_gain
        self.max_size = max_size
        self._lock = threading.RLock()
        self._cache = {}
        self._manifest_path = self.directory / "versions.json"
        self._versions = []
        self._active_version = None
        self._counter = 0
        self._messages = 0
        self._raw_bytes = 0
        self._encoded_bytes = 0
        self._decoded = 0
        self._load_locked()

    # ----- 持久化 -----

    def _load_locked(self):
        if not self._manifest_path.exists():
            return
        manifest = json.loads(self._manifest_path.read_text("utf-8"))
        self._versions = list(manifest.get("versions", []))
        self._active_version = manifest.get("active")
        self._counter = int(manifest.get("counter", 0))
        for entry in self._versions:
            if not (self.directory / entry["file"]).exists():
                raise FormatError("字典版本 %s 的文件丢了" % entry["version"])
        if (self._active_version is not None
                and not self._has_version_locked(self._active_version)):
            raise FormatError(
                "清单里的现役版本 %s 不在库中" % self._active_version)

    def _save_locked(self):
        manifest = {
            "versions": self._versions,
            "active": self._active_version,
            "counter": self._counter,
        }
        temporary = self._manifest_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, indent=2), "utf-8")
        temporary.replace(self._manifest_path)

    def _has_version_locked(self, version):
        return any(entry["version"] == version for entry in self._versions)

    def _entry_locked(self, version):
        for entry in self._versions:
            if entry["version"] == version:
                return entry
        return None

    def _dictionary_locked(self, version):
        dictionary = self._cache.get(version)
        if dictionary is None:
            entry = self._entry_locked(version)
            if entry is None:
                raise DictVersionError(version)
            dictionary = (self.directory / entry["file"]).read_bytes()
            self._cache[version] = dictionary
        return dictionary

    # ----- 属性与统计 -----

    @property
    def active_version(self):
        """当前现役字典版本；没有任何字典时为 None。"""
        with self._lock:
            return self._active_version

    def versions(self):
        """库里现存的字典版本号，按上线先后从老到新。"""
        with self._lock:
            return [entry["version"] for entry in self._versions]

    def dictionary(self, version):
        """取某版本的字典字节；没了（从未上线或已淘汰）抛 DictVersionError。"""
        with self._lock:
            return self._dictionary_locked(version)

    def stats(self):
        """累计统计快照，编码口径与 MessageCodec.stats 相同。"""
        with self._lock:
            ratio = (self._encoded_bytes / self._raw_bytes
                     if self._raw_bytes else 0.0)
            return {
                "messages": self._messages,
                "raw_bytes": self._raw_bytes,
                "encoded_bytes": self._encoded_bytes,
                "decoded": self._decoded,
                "ratio": ratio,
                "active_version": self._active_version,
            }

    # ----- 编解码 -----

    def encode(self, data):
        """把 bytes 编成帧；有现役字典就带字典，否则发无字典帧。"""
        data = bytes(data)
        with self._lock:
            version = self._active_version
            if version is None:
                packed = _build_plain_frame(data)
            else:
                packed = _build_dict_frame(
                    data, self._dictionary_locked(version), version)
            self._messages += 1
            self._raw_bytes += len(data)
            self._encoded_bytes += len(packed)
        return packed

    def decode(self, frame):
        """把帧解回原文。

        无字典老帧（种类 0/1）直接解；带字典帧按帧头版本号取字典，
        版本不存在或已淘汰抛带版本号的 DictVersionError，绝不拿别版
        硬解。长度与校验和不过一律 FormatError，不吐半截数据。
        """
        kind, raw_len, payload, checksum = frame_mod.unpack_frame(frame)
        if kind == frame_mod.KIND_RAW:
            data = payload
        elif kind == frame_mod.KIND_LZ:
            data = lz.decompress(payload, max_size=raw_len)
        else:
            version, pos = lz.decode_varint(payload, 0)
            with self._lock:
                if not self._has_version_locked(version):
                    raise DictVersionError(version)
                dictionary = self._dictionary_locked(version)
            data = lz.decompress(payload[pos:], preset=dictionary,
                                 max_size=raw_len)
        if len(data) != raw_len:
            raise FormatError(
                "解出 %d 字节，帧头写的是 %d 字节" % (len(data), raw_len))
        if frame_mod.fnv32(data) != checksum:
            raise FormatError("校验和对不上，帧坏了或字典版本不对")
        with self._lock:
            self._decoded += 1
        return data

    # ----- 训练与上线 -----

    def rollout(self, samples):
        """训一本新字典并实测，强过现役 min_gain 才上线，否则原样退回。

        样本切成训练集与评测集（80/20，少于 20 条时全部两用）：字典只
        见训练集，编码比率只在没见过的评测集上量，免得新字典在自己的
        训练语料上占“过拟合”的便宜。

        返回报告 dict：是否上线、轮次版本号、训练耗时、字典体积、
        训练/评测条数、无字典/现役基线与候选在评测集上的实测编码总量
        及比率、绝对收益，以及未上线时的原因。“原样退回”指现役字典
        与现役版本一字不变。
        """
        samples = [bytes(sample) for sample in samples]
        with self._lock:
            candidate_version = self._counter + 1

            if len(samples) >= 20:
                cut = len(samples) * 4 // 5
                train_samples = samples[:cut]
                eval_samples = samples[cut:]
            else:
                train_samples = samples
                eval_samples = samples

            started = time.perf_counter()
            dictionary = train_dictionary(train_samples, self.max_size)
            train_seconds = time.perf_counter() - started

            raw_total = sum(len(sample) for sample in eval_samples)
            if self._active_version is None:
                baseline_version = None
                baseline_frames = [_build_plain_frame(sample)
                                   for sample in eval_samples]
            else:
                baseline_version = self._active_version
                active_dict = self._dictionary_locked(baseline_version)
                baseline_frames = [
                    _build_dict_frame(sample, active_dict, baseline_version)
                    for sample in eval_samples]
            candidate_frames = [
                _build_dict_frame(sample, dictionary, candidate_version)
                for sample in eval_samples]
            if not dictionary:
                # 空字典走 _build_dict_frame 会退回无字典帧，gain 被算成
                # 0；如实记账：空字典没有任何命中，带版本头只有纯开销。
                candidate_frames = [
                    frame_mod.pack_frame(
                        frame_mod.KIND_LZ_DICT, len(sample),
                        lz.encode_varint(candidate_version)
                        + lz.compress(sample),
                        frame_mod.fnv32(sample))
                    for sample in eval_samples]
            baseline_total = sum(len(frame) for frame in baseline_frames)
            candidate_total = sum(len(frame) for frame in candidate_frames)
            baseline_ratio = (baseline_total / raw_total
                              if raw_total else 0.0)
            candidate_ratio = (candidate_total / raw_total
                               if raw_total else 0.0)
            gain = baseline_ratio - candidate_ratio

            report = {
                "promoted": False,
                "version": candidate_version,
                "baseline_version": baseline_version,
                "dict_size": len(dictionary),
                "train_seconds": train_seconds,
                "samples": len(samples),
                "raw_bytes": raw_total,
                "baseline_bytes": baseline_total,
                "candidate_bytes": candidate_total,
                "baseline_ratio": baseline_ratio,
                "candidate_ratio": candidate_ratio,
                "gain": gain,
                "min_gain": self.min_gain,
                "reason": "",
                "train_samples": len(train_samples),
                "eval_samples": len(eval_samples),
            }

            if not dictionary:
                report["reason"] = "训练结果为空，无高频片段可上线"
                self._counter = candidate_version
                self._save_locked()
                return report
            if gain < self.min_gain:
                report["reason"] = (
                    "收益 %.4f 低于门槛 %.4f，现役 %s 保持不变"
                    % (gain, self.min_gain,
                       "无字典" if baseline_version is None
                       else "版本 %d" % baseline_version))
                self._counter = candidate_version
                self._save_locked()
                return report

            filename = "dict-%06d.bin" % candidate_version
            (self.directory / filename).write_bytes(dictionary)
            self._cache[candidate_version] = dictionary
            self._versions.append({
                "version": candidate_version,
                "file": filename,
                "size": len(dictionary),
            })
            self._active_version = candidate_version
            self._counter = candidate_version
            while len(self._versions) > self.max_versions:
                oldest = self._versions.pop(0)
                self._cache.pop(oldest["version"], None)
                stale = self.directory / oldest["file"]
                if stale.exists():
                    stale.unlink()
            self._save_locked()
            report["promoted"] = True
            report["reason"] = (
                "收益 %.4f 达到门槛 %.4f，版本 %d 上线"
                % (gain, self.min_gain, candidate_version))
            return report
