"""审计日志的对外入口。

append 追加一条，序号从 1 开始连着走；每条带内容摘要 digest 和上一条的
摘要 prev，连成一条改一处就断的链。read_all 按写入顺序读回。verify 沿链
核对，默认从最近的检查点起步，deep=True 从第一条核到尾。写入走一把锁，
多个线程一起写不会串序号，链顺序跟着提交顺序走，不会分叉。
"""

import json
import os
import threading
import time

from auditchain.codec import encode_line, record_digest
from auditchain.store import RecordStore

CHAIN_FIELD = "prev"
DIGEST_FIELD = "digest"
GENESIS_PREV = "0" * 64


class AuditLog:
    """本地文件的追加型审计日志。

    path: 日志文件路径，不存在就等第一次写入时建。
    clock: 注入时钟，给新记录打时间戳。
    checkpoint_interval: 每多少条固化一个检查点，verify 默认从最近的
        检查点起步往下核，省得每次从头算。
    """

    def __init__(self, path, clock=time.time, checkpoint_interval=1000):
        self.path = path
        self._clock = clock
        self._checkpoint_interval = int(checkpoint_interval)
        self._checkpoint_path = path + ".chk"
        self._store = RecordStore(path)
        self._lock = threading.Lock()
        entries, valid_end = self._store.scan()
        records = [record for _, record in entries]
        if records and any(CHAIN_FIELD not in record for record in records):
            # 老版本写的记录没有链字段，就地补链，不拒绝打开。
            records = self._backfill(records)
        elif self._store.size() > valid_end:
            # 尾巴上挂着没写完的半行，截掉，别让它挡住后面的追加。
            self._store.truncate(valid_end)
        self._last = records[-1] if records else None
        self._seq = 0 if self._last is None else int(self._last["seq"])

    def append(self, action, actor="", detail="", ts=None):
        """追加一条审计记录，返回写进去的那条。

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
                CHAIN_FIELD: GENESIS_PREV if self._last is None else self._last[DIGEST_FIELD],
            }
            record[DIGEST_FIELD] = record_digest(record)
            end = self._store.append(record)
            self._last = record
            self._seq = seq
            if self._checkpoint_due(seq):
                offset = end - len(encode_line(record))
                self._append_checkpoint(seq, offset, record[DIGEST_FIELD])
            return dict(record)

    def read_all(self):
        """按写入顺序读回全部记录。文件坏了抛 CorruptLogError。"""
        entries, _ = self._store.scan()
        return [record for _, record in entries]

    def last(self):
        """最新一条记录的副本，空日志返回 None。"""
        return None if self._last is None else dict(self._last)

    def count(self):
        """记录条数。"""
        return self._seq

    def verify(self, deep=False):
        """沿链核对记录，返回 {"ok", "first_bad", "last_good", "checked"}。

        默认从最近的检查点起步往下核，checked 是这次真算了的条数；
        deep=True 从第一条核起，一条不漏。first_bad 是第一条对不上的
        记录的序号，last_good 是最后一个还一致的记录的序号；末尾写了
        一半的、被截掉的尾巴不算坏，last_good 就落在最后一条完整且
        一致的记录上。
        """
        anchor = None if deep else self._find_anchor()
        if anchor is None:
            start, expected, prev, last_good, checked = 0, 1, GENESIS_PREV, None, 0
        else:
            start, last_good, prev = anchor
            expected = last_good + 1
            checked = 1  # 锚定检查点时也真算了那一条
        entries, corrupt_offset = self._store.scan_prefix(start=start)
        first_bad = None
        for _, record in entries:
            checked += 1
            seq = record.get("seq")
            if (
                seq != expected
                or record.get(CHAIN_FIELD) != prev
                or record_digest(record) != record.get(DIGEST_FIELD)
            ):
                first_bad = seq if isinstance(seq, int) else expected
                break
            prev = record[DIGEST_FIELD]
            last_good = seq
            expected += 1
        if first_bad is None and corrupt_offset is not None:
            first_bad = expected
        return {
            "ok": first_bad is None,
            "first_bad": first_bad,
            "last_good": last_good,
            "checked": checked,
        }

    def _checkpoint_due(self, seq):
        """这条序号该不该固化检查点。"""
        return self._checkpoint_interval > 0 and seq % self._checkpoint_interval == 0

    def _append_checkpoint(self, seq, offset, digest):
        """把一条检查点追加到检查点文件。"""
        line = json.dumps(
            {"seq": seq, "offset": offset, "digest": digest},
            separators=(",", ":"),
        )
        with open(self._checkpoint_path, "a", encoding="ascii") as handle:
            handle.write(line + "\n")

    def _write_checkpoints(self, records):
        """按现有记录整份重建检查点文件。"""
        lines = []
        offset = 0
        for record in records:
            blob = encode_line(record)
            if self._checkpoint_due(record["seq"]):
                lines.append(
                    json.dumps(
                        {"seq": record["seq"], "offset": offset, "digest": record[DIGEST_FIELD]},
                        separators=(",", ":"),
                    )
                )
            offset += len(blob)
        if lines:
            with open(self._checkpoint_path, "w", encoding="ascii") as handle:
                handle.write("\n".join(lines) + "\n")
        elif os.path.exists(self._checkpoint_path):
            os.remove(self._checkpoint_path)

    def _load_checkpoints(self):
        """读出全部检查点，文件没有或某行坏了就跳过，不因此报错。"""
        try:
            with open(self._checkpoint_path, "rb") as handle:
                data = handle.read()
        except OSError:
            return []
        checkpoints = []
        for line in data.splitlines():
            try:
                point = json.loads(line.decode("ascii"))
                checkpoints.append(
                    {
                        "seq": int(point["seq"]),
                        "offset": int(point["offset"]),
                        "digest": str(point["digest"]),
                    }
                )
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                continue
        return checkpoints

    def _find_anchor(self):
        """最近一个对得上的检查点，返回 (下一条的偏移, 检查点序号, 摘要)。

        检查点记录本身要重新算一遍摘要来对；对不上说明检查点之前的
        历史不可信，返回 None 让调用方从头核。没有检查点也返回 None。
        """
        checkpoints = self._load_checkpoints()
        if not checkpoints:
            return None
        point = checkpoints[-1]
        got = self._store.read_at(point["offset"])
        if got is None:
            return None
        record, next_offset = got
        if (
            record.get("seq") != point["seq"]
            or record.get(DIGEST_FIELD) != point["digest"]
            or record_digest(record) != point["digest"]
        ):
            return None
        return next_offset, point["seq"], point["digest"]

    def _backfill(self, records):
        """给老版本写的记录就地补链：重算 prev 和 digest，整份重写。"""
        prev = GENESIS_PREV
        chained = []
        for record in records:
            record = dict(record)
            record[CHAIN_FIELD] = prev
            record[DIGEST_FIELD] = record_digest(record)
            chained.append(record)
            prev = record[DIGEST_FIELD]
        self._store.rewrite(chained)
        self._write_checkpoints(chained)
        return chained
