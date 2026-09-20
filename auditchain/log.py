"""审计日志的对外入口。

append 追加一条，序号从 1 开始连着走。每条记录除了内容摘要 digest，
还带上一条记录的摘要 prev_digest，形成一条哈希链：改掉任何一条的
内容，它自己的 digest 先对不上，后面记录的 prev_digest 也跟着断链。

每 N 条固化一个检查点到侧车文件，verify() 默认从最近检查点起步往下
核；出了事传 deep=True 从第 1 条整链重核。老版本写的、没有链字段
的日志，打开时就地补链，不拒绝使用。写入走一把锁，多个线程一起写，
链顺序严格跟着提交顺序走，不会分叉。
"""

import hashlib
import threading
import time

from auditchain.codec import (
    GENESIS_DIGEST,
    PREV_DIGEST_FIELD,
    canonical,
    record_digest,
)
from auditchain.store import CheckpointStore, RecordStore


CHECKPOINT_SIGNATURE_FIELD = "sig"


class AuditLog:
    """本地文件的追加型审计日志。

    path: 日志文件路径，不存在就等第一次写入时建。
    clock: 注入时钟，给新记录打时间戳。
    checkpoint_every: 每写多少条固化一个检查点，<=0 表示不固化。
    """

    def __init__(self, path, clock=time.time, checkpoint_every=1000):
        self.path = path
        self._clock = clock
        self._store = RecordStore(path)
        self._checkpoints = CheckpointStore(self.checkpoint_path)
        self._checkpoint_every = int(checkpoint_every)
        self._lock = threading.Lock()
        self._entries = []
        self._end_offset = 0
        self._last = None
        self._seq = 0
        self._load()

    @property
    def checkpoint_path(self):
        """检查点侧车文件的路径，和日志文件放一块。"""
        return self.path + ".ckpt"

    def append(self, action, actor="", detail="", ts=None):
        """追加一条审计记录，返回写进去的那条。

        返回的是副本，调用方拿去改不影响日志里的内容。
        """
        with self._lock:
            seq = self._seq + 1
            prev_digest = GENESIS_DIGEST if self._last is None else self._last["digest"]
            record = {
                "seq": seq,
                "ts": float(self._clock() if ts is None else ts),
                "action": action,
                "actor": actor,
                "detail": detail,
                PREV_DIGEST_FIELD: prev_digest,
            }
            record["digest"] = record_digest(record)
            end_offset = self._store.append(record)
            self._last = record
            self._entries.append((self._end_offset, record))
            self._end_offset = end_offset
            self._seq = seq
            if self._checkpoint_every > 0 and seq % self._checkpoint_every == 0:
                self._persist_checkpoint(record, end_offset)
            return dict(record)

    def read_all(self):
        """按写入顺序读回全部记录。文件坏了抛 CorruptLogError。"""
        entries, _ = self._store.scan()
        return [dict(record) for _, record in entries]

    def last(self):
        """最新一条记录的副本，空日志返回 None。"""
        return None if self._last is None else dict(self._last)

    def count(self):
        """记录条数。"""
        return self._seq

    def verify(self, deep=False):
        """校验哈希链，返回核对结果。

        返回 dict，键固定四个：
        - ok: 链是否完整一致
        - first_bad: 第一处问题的记录号（第几条），没问题为 None；
          检查点之后的整段被截掉时，是第一个缺失的号
        - last_good: 最后一个一致点的记录号，一条都不成立为 0
        - checked: 这次实际从头算摘要核对了几条

        deep=False（默认）从最近一个有效检查点的锚点记录起步往下核，
        巡检不用每次从头算；deep=True 从第 1 条整链重核，一条不漏。
        尾部没写完的半行不算坏，只认到最后一个一致点。
        """
        with self._lock:
            entries, _ = self._store.scan()
            checkpoint = self._latest_good_checkpoint()

            if not entries:
                return {
                    "ok": checkpoint is None,
                    "first_bad": None if checkpoint is None else 1,
                    "last_good": 0,
                    "checked": 0,
                }

            start = 0
            anchor = None
            if not deep and checkpoint is not None:
                anchor_seq = int(checkpoint["seq"])
                if 1 <= anchor_seq <= len(entries) and self._anchor_matches(
                    entries[anchor_seq - 1][1], checkpoint
                ):
                    anchor_record = entries[anchor_seq - 1][1]
                    if self._record_self_consistent(anchor_record, anchor_seq):
                        start = anchor_seq - 1
                        anchor = anchor_record
                    # 锚点自身都对不上内容，检查点不能信，退回整链重核。

            prev_digest = GENESIS_DIGEST if anchor is None else anchor["digest"]
            checked = 0
            for index in range(start, len(entries)):
                record = entries[index][1]
                checked += 1
                if anchor is not None and index == start:
                    expected_prev = None
                else:
                    expected_prev = prev_digest
                if not self._record_matches(record, index + 1, expected_prev):
                    return {
                        "ok": False,
                        "first_bad": index + 1,
                        "last_good": index,
                        "checked": checked,
                    }
                prev_digest = record["digest"]

            last_good = len(entries)
            if checkpoint is not None and int(checkpoint["seq"]) > last_good:
                return {
                    "ok": False,
                    "first_bad": last_good + 1,
                    "last_good": last_good,
                    "checked": checked,
                }

            return {"ok": True, "first_bad": None, "last_good": last_good, "checked": checked}

    def _load(self):
        """打开日志：扫盘、丢掉半行尾巴、给老日志补链、载入内存状态。"""
        entries, valid_end = self._store.scan()
        if entries:
            if self._store.size() > valid_end:
                self._store.truncate(valid_end)
            if self._is_legacy(entries):
                entries, valid_end = self._backfill_chain(entries)
        self._entries = entries
        self._end_offset = valid_end
        if entries:
            self._last = entries[-1][1]
            self._seq = len(entries)

    @staticmethod
    def _is_legacy(entries):
        """老版本写的日志：一条链字段都没有。

        只看首条会被手删字段骗过——新格式日志删掉首条 prev_digest
        会呈现"混合"状态，绝不能就地重链把篡改洗白。
        """
        return all(PREV_DIGEST_FIELD not in record for _, record in entries)

    def _backfill_chain(self, entries):
        """老日志就地补链：重算 digest、加 prev_digest，原子重写整文件。"""
        rebuilt = []
        prev_digest = GENESIS_DIGEST
        end_offset = 0
        for _, old_record in entries:
            record = dict(old_record)
            record[PREV_DIGEST_FIELD] = prev_digest
            record["digest"] = record_digest(record)
            rebuilt.append(record)
            prev_digest = record["digest"]
            end_offset += len(canonical(record)) + 1
            if self._checkpoint_every > 0 and len(rebuilt) % self._checkpoint_every == 0:
                self._persist_checkpoint(record, end_offset)
        self._store.rewrite_all(rebuilt)
        return self._store.scan()

    def _persist_checkpoint(self, record, end_offset_at):
        """固化一个检查点，签名覆盖 seq/digest/offset，防止侧车被手改。"""
        entry = {
            "seq": int(record["seq"]),
            "digest": record["digest"],
            "offset": int(end_offset_at) if end_offset_at is not None else 0,
        }
        entry[CHECKPOINT_SIGNATURE_FIELD] = self._checkpoint_signature(entry)
        self._checkpoints.append(entry)

    def _latest_good_checkpoint(self):
        """取最近一个签名和字段都站得住的检查点，站不住的一律忽略。"""
        good = None
        for entry in self._checkpoints.read_all():
            if self._checkpoint_is_valid(entry):
                seq = int(entry["seq"])
                if good is None or seq > int(good["seq"]):
                    good = entry
        return good

    @staticmethod
    def _checkpoint_signature(entry):
        """检查点签名：对 seq/digest/offset 的规范编码取 sha256。"""
        payload = {
            key: entry[key]
            for key in ("seq", "digest", "offset")
            if key in entry
        }
        return hashlib.sha256(canonical(payload)).hexdigest()

    def _checkpoint_is_valid(self, entry):
        """检查点字段齐全、签名对得上才算数。"""
        try:
            seq = int(entry["seq"])
            digest = entry["digest"]
            offset = int(entry["offset"])
            signature = entry[CHECKPOINT_SIGNATURE_FIELD]
        except (KeyError, TypeError, ValueError):
            return False
        if seq < 1 or not isinstance(digest, str) or offset < 0:
            return False
        if not isinstance(signature, str):
            return False
        expected = self._checkpoint_signature(
            {"seq": seq, "digest": digest, "offset": offset}
        )
        return signature == expected

    def _anchor_matches(self, record, checkpoint):
        """检查点锚点和磁盘上那条记录是不是同一条（同号同摘要）。"""
        return (
            isinstance(record.get("digest"), str)
            and record["digest"] == checkpoint["digest"]
        )

    @staticmethod
    def _record_self_consistent(record, expected_seq):
        """只查序号和内容摘要，不碰前链，给锚点起步用。"""
        if not isinstance(record, dict) or type(record.get("seq")) is not int:
            return False
        if record["seq"] != expected_seq:
            return False
        digest = record.get("digest")
        return isinstance(digest, str) and digest == record_digest(record)

    @staticmethod
    def _record_matches(record, expected_seq, expected_prev):
        """一条记录是否自洽：内容摘要、前链指针、序号三项都要对。

        expected_prev 为 None 时不查前链（只做锚点自洽性检查）。
        """
        if not AuditLog._record_self_consistent(record, expected_seq):
            return False
        prev_digest = record.get(PREV_DIGEST_FIELD)
        if not isinstance(prev_digest, str):
            return False
        if expected_prev is not None and prev_digest != expected_prev:
            return False
        return True
