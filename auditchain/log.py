"""审计日志的对外入口。

append 追加一条，序号从 1 开始连着走。每条记录带着上一条的摘要
prev，自己的内容摘要 digest 连 prev 一起算，所以改掉中间任何一条，
它之后的链就全断了。read_all 按写入顺序读回。

verify() 核链，返回 ok / first_bad / last_good / checked：

- 默认巡检：从最近一个检查点往下核，checked 是这次真算了几条；
- deep=True：从第 1 条起重算，一条不漏，改掉的那条报它的 seq，
  同时拿检查点对条数，认出被截掉的整段尾巴。

上一版写的老日志没有链字段，打开时就地原子补链，不当坏文件拒绝。
写入走一把锁，多线程 append 的链顺序严格跟着提交顺序走，不分叉。
"""

import threading
import time

from auditchain.checkpoints import CheckpointStore
from auditchain.codec import (
    GENESIS_PREV,
    PREV_FIELD,
    record_digest,
)
from auditchain.store import RecordStore

DEFAULT_CHECKPOINT_EVERY = 1000


class AuditLog:
    """本地文件的追加型审计日志。

    path: 日志文件路径，不存在就等第一次写入时建。
    clock: 注入时钟，给新记录打时间戳。
    checkpoint_every: 每多少条固化一个检查点。
    """

    def __init__(self, path, clock=time.time, checkpoint_every=DEFAULT_CHECKPOINT_EVERY):
        self.path = path
        self._clock = clock
        if not isinstance(checkpoint_every, int) or isinstance(checkpoint_every, bool):
            raise TypeError("checkpoint_every must be an int")
        if checkpoint_every < 1:
            raise ValueError("checkpoint_every must be >= 1")
        self._checkpoint_every = checkpoint_every
        self._store = RecordStore(path)
        self._checkpoints = CheckpointStore(path + ".ckpt")
        self._lock = threading.Lock()
        self._bootstrap()

    def append(self, action, actor="", detail="", ts=None):
        """追加一条审计记录，返回写进去的那条。

        prev 取提交时上一条的摘要，多线程下链顺序与提交顺序一致。
        返回的是副本，调用方拿去改不影响日志里的内容。
        """
        with self._lock:
            seq = self._seq + 1
            record = {
                "seq": seq,
                "ts": float(self._clock() if ts is None else ts),
                "action": action,
                "actor": actor,
                "detail": detail,
                PREV_FIELD: GENESIS_PREV if self._last is None else self._last["digest"],
            }
            record["digest"] = record_digest(record)
            offset = self._store.append(record)
            if seq % self._checkpoint_every == 0:
                self._checkpoints.append(
                    seq, record["digest"], record[PREV_FIELD], offset - 1
                )
            self._last = record
            self._seq = seq
            return dict(record)

    def read_all(self):
        """按写入顺序读回全部记录。文件坏了抛 CorruptLogError。"""
        with self._lock:
            entries, _ = self._store.scan()
            return [dict(record) for _, record in entries]

    def last(self):
        """最新一条记录的副本，空日志返回 None。"""
        return None if self._last is None else dict(self._last)

    def count(self):
        """完整记录条数（半行尾巴不算）。"""
        return self._seq

    def verify(self, deep=False):
        """核对防篡改链。

        返回 dict：

        - ok: 这次核对范围内是否全部一致；
        - first_bad: 第一条对不上的记录序号，没问题或只发现尾巴丢失时
          为 None；
        - last_good: 最后一个一致点的记录序号，一条都没立住为 None；
        - checked: 这次真重算了几条记录。

        deep=False（巡检）时从最近一个检查点往下核，检查点之前的不重算；
        没有可用检查点则从头核。deep=True 时从第 1 条重算全链，并用
        检查点识别被整段截掉的尾巴。
        """
        with self._lock:
            entries, valid_end = self._store.scan()
            records = [record for _, record in entries]
            n = len(records)
            all_anchors = self._checkpoints.load()
            tail_lost = any(anchor["seq"] > n for anchor in all_anchors)
            anchors = [anchor for anchor in all_anchors if anchor["seq"] <= n]

            # deep、没有锚点可用、或尾巴已经被截到锚点之后：从头核。
            if deep or not records or not anchors or tail_lost:
                result = self._verify_walk(records, 0)
                result["checked"] = n
                anchor_clash = None
                if deep and result["first_bad"] is None:
                    anchor_clash = self._first_clashing_anchor(records, anchors)
                if result["first_bad"] is None and (tail_lost or anchor_clash is not None):
                    result["ok"] = False
                    if tail_lost:
                        result["last_good"] = None if n == 0 else n
                    else:
                        result["first_bad"] = anchor_clash["seq"]
                        result["last_good"] = anchor_clash["seq"] - 1
                return result

            anchor = max(anchors, key=lambda candidate: candidate["seq"])
            anchor_index = anchor["seq"] - 1
            anchor_record = records[anchor_index]
            recomputed = record_digest(anchor_record)
            if (
                not self._record_self_matches(anchor_record)
                or recomputed != anchor["digest"]
                or anchor_record.get(PREV_FIELD) != anchor["prev"]
                or self._seq_of(anchor_record) != anchor["seq"]
            ):
                result = self._verify_walk(records, 0)
                result["checked"] = n
                return result

            result = self._verify_walk(records, anchor_index)
            result["checked"] = n - anchor_index
            return result

    # ---- 打开日志时的自愈：截半行、补老链、对检查点 ----

    def _bootstrap(self):
        """打开日志：认得最后一个一致点，老日志就地补链。"""
        entries, valid_end = self._store.scan()

        if self._store.size() > valid_end:
            self._store.truncate(valid_end)

        migrated = any(PREV_FIELD not in record for _, record in entries)
        if migrated:
            self._migrate(entries)
            entries, valid_end = self._store.scan()

        if not entries:
            self._last = None
            self._seq = 0
            return

        self._last = entries[-1][1]
        self._seq = int(self._last["seq"])
        # 只在迁移补链之后重建检查点；平时打开绝不改写对不上的锚点，
        # 那正是 verify() 要拿住的篡改证据。
        if migrated:
            self._rebuild_checkpoints(entries)

    def _migrate(self, entries):
        """老记录（没有 prev）就地补链，原子整文件重写。

        prev 加入了摘要覆盖范围，所以补链同时按新规则重算 digest，
        补完的链与新写入的记录完全同构。
        """
        upgraded = []
        prev_digest = GENESIS_PREV
        for _, record in entries:
            record = dict(record)
            record[PREV_FIELD] = prev_digest
            record["digest"] = record_digest(record)
            upgraded.append(record)
            prev_digest = record["digest"]
        self._store.replace(upgraded)

    def _rebuild_checkpoints(self, entries):
        """迁移补链之后按新链重建全部检查点锚点。"""
        anchors = []
        for seq in range(self._checkpoint_every, self._seq + 1, self._checkpoint_every):
            offset, record = entries[seq - 1]
            anchors.append(
                {
                    "seq": seq,
                    "digest": record_digest(record),
                    PREV_FIELD: record[PREV_FIELD],
                    "offset": offset,
                }
            )
        self._checkpoints.rewrite(anchors)

    # ---- 核链 ----

    @staticmethod
    def _record_self_matches(record):
        """摘要字段重算是否一致。"""
        return record.get("digest") == record_digest(record)

    @staticmethod
    def _seq_of(record):
        """记录里的序号，缺失或类型不对返回 None。"""
        seq = record.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int):
            return None
        return seq

    @staticmethod
    def _first_clashing_anchor(records, anchors):
        """链体自洽但与固化锚点对不上时，最早冲突的那个锚点。

        说明有人改了记录又把整条链重算了，但没能力同步旁路检查点。
        """
        for anchor in sorted(anchors, key=lambda candidate: candidate["seq"]):
            record = records[anchor["seq"] - 1]
            if (
                record_digest(record) != anchor["digest"]
                or record.get(PREV_FIELD) != anchor["prev"]
            ):
                return anchor
        return None

    def _verify_walk(self, records, start_index):
        """从第 start_index 条（0 基，检查点锚点本身也重算）顺序核链。"""
        n = len(records)
        for index in range(start_index, n):
            record = records[index]
            expected_seq = index + 1
            if index == 0:
                prev_ok = record.get(PREV_FIELD) == GENESIS_PREV
            elif index == start_index and start_index > 0:
                prev_ok = True
            else:
                prev_ok = record.get(PREV_FIELD) == records[index - 1].get("digest")
            if (
                self._seq_of(record) != expected_seq
                or not self._record_self_matches(record)
                or not prev_ok
            ):
                return {
                    "ok": False,
                    "first_bad": expected_seq,
                    "last_good": None if index == 0 else index,
                    "checked": index - start_index + 1,
                }
        return {
            "ok": True,
            "first_bad": None,
            "last_good": None if n == 0 else n,
            "checked": n - start_index,
        }
