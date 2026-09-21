"""审计日志的对外入口。

append 追加一条，序号从 1 开始连着走，每条带内容摘要 digest 和上一条
的摘要 prev，串成防篡改链；read_all 按写入顺序读回；verify 校验整条
链，默认从最近的检查点起步，deep=True 整链重核。写入走一把锁，多个
线程一起写不会串序号，链顺序跟着提交顺序走，不分叉。
"""

import os
import threading
import time

from auditchain.codec import RecordError, decode_line, encode_line, record_digest
from auditchain.store import CorruptLogError, RecordStore

GENESIS_PREV = "0" * 64
CHECKPOINT_SUFFIX = ".chk"


class AuditLog:
    """本地文件的追加型审计日志。

    path: 日志文件路径，不存在就等第一次写入时建。
    clock: 注入时钟，给新记录打时间戳。
    checkpoint_every: 每多少条固化一个检查点，verify 默认从最近的
        检查点起步往下核，不必每次从头算。
    """

    def __init__(self, path, clock=time.time, checkpoint_every=1000):
        self.path = path
        self._clock = clock
        self._checkpoint_every = max(1, int(checkpoint_every))
        self._checkpoint_path = path + CHECKPOINT_SUFFIX
        self._store = RecordStore(path)
        self._lock = threading.Lock()
        self._migrate_legacy()
        self._last = self._load_last()
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
            }
            record["prev"] = GENESIS_PREV if self._last is None else self._last["digest"]
            record["digest"] = record_digest(record)
            self._store.append(record)
            if seq % self._checkpoint_every == 0:
                self._write_checkpoint(seq, record["digest"])
            self._last = record
            self._seq = seq
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
        """校验防篡改链，返回 {"ok", "first_bad", "last_good", "checked"}。

        默认从最近的检查点起步往下核，checked 是这次真算了的条数；
        deep=True 从第一条整链重核，一条不漏。first_bad 是第一条对不上
        的记录的序号，last_good 是最后一个一致点的序号（一条都算不上时
        为 None）。末尾没写完的半行不参与校验，不因此报错；中间解不开
        的行、被截掉的尾巴都会报出位置，不让整个库报废。
        """
        try:
            entries, _ = self._store.scan()
        except CorruptLogError as exc:
            # 中间有解不开的行：核它前面的完整前缀，坏行就是第一个对不上的位置
            records = [record for _, record in self._scan_prefix(exc.offset or 0)]
            return self._report_broken_tail(records, self._verify_records(records, 0))

        records = [record for _, record in entries]
        checkpoints = [] if deep else self._load_checkpoints()
        if checkpoints and checkpoints[-1][0] > len(records):
            # 检查点越过了文件末尾：尾巴被截过，整链重核找最后一致点
            return self._report_broken_tail(records, self._verify_records(records, 0))

        start = 0
        prev = GENESIS_PREV
        if checkpoints:
            start, prev = checkpoints[-1]
        return self._verify_records(records, start, prev)

    @staticmethod
    def _report_broken_tail(records, result):
        """现存记录都一致但后面确定缺了记录时，把缺口报成 first_bad。"""
        if result["ok"]:
            result["ok"] = False
            result["first_bad"] = len(records) + 1
            result["last_good"] = len(records) or None
        return result

    @staticmethod
    def _verify_records(records, start, prev=GENESIS_PREV):
        """从 start（0 基）往下逐条核，prev 是 start 前一条的可信摘要。"""
        checked = 0
        last_good = start or None
        for index in range(start, len(records)):
            record = records[index]
            checked += 1
            if (
                record.get("seq") != index + 1
                or record.get("prev") != prev
                or record_digest(record) != record.get("digest")
            ):
                return {
                    "ok": False,
                    "first_bad": index + 1,
                    "last_good": last_good,
                    "checked": checked,
                }
            prev = record["digest"]
            last_good = index + 1
        return {"ok": True, "first_bad": None, "last_good": last_good, "checked": checked}

    def _scan_prefix(self, end_offset):
        """只扫 end_offset 之前的完整行，给中间坏行前面的前缀用。"""
        try:
            with open(self.path, "rb") as handle:
                data = handle.read(end_offset)
        except FileNotFoundError:
            return []
        entries = []
        offset = 0
        while offset < len(data):
            newline = data.find(b"\n", offset)
            if newline < 0:
                break
            entries.append((offset, decode_line(data[offset:newline])))
            offset = newline + 1
        return entries

    def _write_checkpoint(self, seq, digest):
        """固化一个检查点：序号加当时的链头摘要，一行一条追加。"""
        with open(self._checkpoint_path, "ab") as handle:
            handle.write(encode_line({"seq": seq, "digest": digest}))
            handle.flush()

    def _load_checkpoints(self):
        """读回全部检查点，文件没有或个别行坏了就当没有，回退到从头核。"""
        checkpoints = []
        try:
            with open(self._checkpoint_path, "rb") as handle:
                data = handle.read()
        except FileNotFoundError:
            return checkpoints
        for line in data.split(b"\n"):
            if not line:
                continue
            try:
                item = decode_line(line)
            except RecordError:
                continue
            seq = item.get("seq")
            digest = item.get("digest")
            if isinstance(seq, int) and isinstance(digest, str):
                checkpoints.append((seq, digest))
        return checkpoints

    def _migrate_legacy(self):
        """老版本日志没有链字段，开库时就地补链而不是拒绝打开。

        逐条补上 prev、重算 digest，原子重写日志文件，顺手把检查点
        也补齐；尾巴上没写完的半行随重写一起丢掉。
        """
        entries, _ = self._store.scan()
        records = [record for _, record in entries]
        if not records or all("prev" in record for record in records):
            return
        prev = GENESIS_PREV
        chained = []
        checkpoints = []
        for index, record in enumerate(records):
            record = dict(record)
            record.pop("digest", None)
            record["prev"] = prev
            record["digest"] = record_digest(record)
            prev = record["digest"]
            chained.append(record)
            seq = index + 1
            if seq % self._checkpoint_every == 0:
                checkpoints.append((seq, record["digest"]))
        tmp_path = self.path + ".migrate.tmp"
        with open(tmp_path, "wb") as handle:
            for record in chained:
                handle.write(encode_line(record))
        os.replace(tmp_path, self.path)
        with open(self._checkpoint_path, "wb") as handle:
            for seq, digest in checkpoints:
                handle.write(encode_line({"seq": seq, "digest": digest}))

    def _load_last(self):
        """开日志时扫一遍，拿到最后一条完整记录。"""
        entries, _ = self._store.scan()
        if not entries:
            return None
        return entries[-1][1]
