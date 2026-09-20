"""内存倒排索引 + 写前日志（WAL）+ 定期全量落盘。

每次变更先把记录追加到 WAL 并 fsync，落住之后再改内存。
重启时先读快照，再顺序重放快照之后留下的日志；日志里的最后
一条可能因为掉电只写了一半，按长度与校验和识别后截断丢弃。
"""
import json
import os
import re
import tempfile
import threading
import zlib

SNAPSHOT_NAME = "index.snapshot.json"
WAL_NAME = "index.wal.log"
SNAPSHOT_TMP_PREFIX = ".%s.tmp" % SNAPSHOT_NAME
SNAPSHOT_EVERY = 100

# 一条记录："<长度>:<crc32>:<payload-json>\n"
# 长度 + 校验和用于识别写到一半的坏记录（见 _decode_record）。
_RECORD_HEAD = re.compile(rb"^(\d+):([0-9a-f]{8}):")


def tokenize(text):
    """小写按空白切词，去重后排序。"""
    return sorted(set(text.lower().split()))


def _encode_record(op, doc_id, text):
    payload = json.dumps([op, doc_id, text], ensure_ascii=False).encode("utf-8")
    checksum = zlib.crc32(payload) & 0xFFFFFFFF
    return ("%d:%08x:" % (len(payload), checksum)).encode("ascii") + payload + b"\n"


def _decode_record(line):
    """解析一行日志。坏行（写了一半/校验不过）返回 None。"""
    match = _RECORD_HEAD.match(line)
    if not match:
        return None
    length, expected_crc = int(match.group(1)), int(match.group(2), 16)
    start = match.end()
    payload = line[start:]
    if line.endswith(b"\n"):
        payload = payload[:-1]
    if len(payload) != length or (zlib.crc32(payload) & 0xFFFFFFFF) != expected_crc:
        return None
    try:
        record = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if (not isinstance(record, list) or len(record) != 3
            or record[0] not in ("put", "delete")):
        return None
    return record


class IndexStore:
    """正排（doc_id -> 原文）与倒排（term -> doc_id 集合）都在内存里。"""

    def __init__(self, directory, snapshot_every=SNAPSHOT_EVERY):
        self._dir = directory
        self._snapshot_every = snapshot_every
        self._docs = {}
        self._postings = {}
        self._ops = 0
        # 所有变更（日志追加 + 内存改动 + 快照裁剪）走同一把锁，
        # 保证日志里的先后顺序与内存真正生效的顺序一致。
        self._lock = threading.RLock()
        self._wal = None
        os.makedirs(directory, exist_ok=True)

    # -- 查询 ---------------------------------------------------------
    def get(self, doc_id):
        with self._lock:
            return self._docs.get(doc_id)

    def search(self, term):
        with self._lock:
            return sorted(self._postings.get(term.lower(), ()))

    def doc_count(self):
        with self._lock:
            return len(self._docs)

    def close(self):
        """关闭日志句柄（不触发快照）。"""
        with self._lock:
            if self._wal is not None:
                self._wal.close()
                self._wal = None

    def __del__(self):
        wal = getattr(self, "_wal", None)
        if wal is not None:
            wal.close()

    # -- 变更 ---------------------------------------------------------
    def put(self, doc_id, text):
        with self._lock:
            self._log_change("put", doc_id, text)
            self._apply_put(doc_id, text)
            self._after_change()

    def delete(self, doc_id):
        with self._lock:
            if doc_id not in self._docs:
                return
            self._log_change("delete", doc_id, None)
            self._apply_delete(doc_id)
            self._after_change()

    def _unindex(self, doc_id):
        text = self._docs.pop(doc_id)
        for term in tokenize(text):
            bucket = self._postings.get(term)
            if bucket:
                bucket.discard(doc_id)
                if not bucket:
                    del self._postings[term]

    def _apply_put(self, doc_id, text):
        if doc_id in self._docs:
            self._unindex(doc_id)
        self._docs[doc_id] = text
        for term in tokenize(text):
            self._postings.setdefault(term, set()).add(doc_id)

    def _apply_delete(self, doc_id):
        if doc_id in self._docs:
            self._unindex(doc_id)

    # -- 写前日志 -----------------------------------------------------
    def _log_change(self, op, doc_id, text):
        if self._wal is None:
            self._wal = open(os.path.join(self._dir, WAL_NAME), "ab")
        self._wal.write(_encode_record(op, doc_id, text))
        self._wal.flush()
        os.fsync(self._wal.fileno())

    def _after_change(self):
        self._ops += 1
        if self._ops >= self._snapshot_every:
            self.snapshot()

    # -- 落盘 / 恢复 --------------------------------------------------
    def snapshot(self):
        """整份索引原子写入快照，落稳后裁剪日志。"""
        with self._lock:
            payload = {"docs": self._docs, "ops": self._ops}
            fd, tmp = tempfile.mkstemp(dir=self._dir, prefix=SNAPSHOT_TMP_PREFIX)
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, os.path.join(self._dir, SNAPSHOT_NAME))
            self._sync_dir()
            # 快照已包含全部状态，日志里的记录重放也是幂等的，
            # 但留着会让恢复白白重放；落稳后立即删掉。
            if self._wal is not None:
                self._wal.close()
                self._wal = None
            wal_path = os.path.join(self._dir, WAL_NAME)
            if os.path.exists(wal_path):
                os.remove(wal_path)
                self._sync_dir()
            self._ops = 0

    def load(self):
        """从快照重建内存，再重放日志补齐快照之后的变更。

        返回载入的文档数（含日志重放结果）。put/delete 的重放都是
        幂等的，所以日志即使覆盖了快照里的状态也不会出错。
        """
        with self._lock:
            self._cleanup_stale_tmp()
            self._docs = {}
            self._postings = {}
            self._ops = 0
            path = os.path.join(self._dir, SNAPSHOT_NAME)
            if os.path.exists(path):
                with open(path) as f:
                    payload = json.load(f)
                self._docs = dict(payload["docs"])
                for doc_id, text in self._docs.items():
                    for term in tokenize(text):
                        self._postings.setdefault(term, set()).add(doc_id)
            self._replay_wal()
            return len(self._docs)

    # -- 日志重放 -----------------------------------------------------
    def _replay_wal(self):
        """顺序重放日志；遇到坏记录（多半写到一半）截断其后全部内容。"""
        wal_path = os.path.join(self._dir, WAL_NAME)
        if not os.path.exists(wal_path):
            return
        good_bytes = 0
        bad_seen = False
        with open(wal_path, "rb") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                record = _decode_record(line)
                if record is None:
                    bad_seen = True
                    break
                op, doc_id, text = record
                if op == "put":
                    self._apply_put(doc_id, text)
                else:
                    self._apply_delete(doc_id)
                good_bytes += len(line)
        if bad_seen:
            # 从第一条坏记录起整段丢弃（掉电时其后也不可能有有效数据），
            # 之后从截断处继续追加。
            with open(wal_path, "r+b") as f:
                f.truncate(good_bytes)
                f.flush()
                os.fsync(f.fileno())
        self._wal = open(wal_path, "ab")

    def _cleanup_stale_tmp(self):
        """杀掉写快照写到一半的进程会残留临时文件，重启时清掉。"""
        for name in os.listdir(self._dir):
            if name.startswith(SNAPSHOT_TMP_PREFIX):
                os.remove(os.path.join(self._dir, name))

    def _sync_dir(self):
        try:
            fd = os.open(self._dir, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        except OSError:
            pass
        finally:
            os.close(fd)
