"""内存倒排索引 + 预写日志（WAL）+ 定期全量落盘。"""
import json
import os
import tempfile
import threading
import zlib

SNAPSHOT_NAME = "index.snapshot.json"
WAL_NAME = "index.wal.jsonl"
SNAPSHOT_EVERY = 100


def tokenize(text):
    """小写按空白切词，去重后排序。"""
    return sorted(set(text.lower().split()))


def _encode_record(record):
    """日志记录序列化为一行 JSON，附带其余字段的 CRC32。"""
    body = json.dumps(record, sort_keys=True)
    crc = zlib.crc32(body.encode("utf-8"))
    return json.dumps(dict(record, crc=crc), sort_keys=True) + "\n"


def _decode_record(line):
    """解析一行日志；JSON 残缺或 CRC 不符（掉电撕写）返回 None。"""
    try:
        record = json.loads(line)
    except ValueError:
        return None
    if not isinstance(record, dict):
        return None
    crc = record.pop("crc", None)
    body = json.dumps(record, sort_keys=True)
    if not isinstance(crc, int) or zlib.crc32(body.encode("utf-8")) != crc:
        return None
    if not isinstance(record.get("seq"), int) or record.get("op") not in ("put", "delete"):
        return None
    if not isinstance(record.get("doc_id"), str):
        return None
    if record["op"] == "put" and not isinstance(record.get("text"), str):
        return None
    return record


class IndexStore:
    """正排（doc_id -> 原文）与倒排（term -> doc_id 集合）都在内存里。

    每次变更先把日志记录追加到 WAL 并 fsync，再改内存；同一把锁包住
    两步，保证日志顺序与内存生效顺序一致。快照记录已覆盖的最大 seq，
    恢复时只重放更新的日志。
    """

    def __init__(self, directory, snapshot_every=SNAPSHOT_EVERY):
        self._dir = directory
        self._snapshot_every = snapshot_every
        self._docs = {}
        self._postings = {}
        self._ops = 0
        self._seq = None  # 未知；load() 或首次变更前从磁盘恢复
        self._lock = threading.RLock()
        self._wal = None
        os.makedirs(directory, exist_ok=True)

    # -- 查询 ---------------------------------------------------------
    def get(self, doc_id):
        return self._docs.get(doc_id)

    def search(self, term):
        return sorted(self._postings.get(term.lower(), ()))

    def doc_count(self):
        return len(self._docs)

    # -- 变更 ---------------------------------------------------------
    def put(self, doc_id, text):
        with self._lock:
            self._ensure_seq()
            self._seq += 1
            self._append_wal({"seq": self._seq, "op": "put",
                              "doc_id": doc_id, "text": text})
            self._apply_put(doc_id, text)
            self._after_change()

    def delete(self, doc_id):
        with self._lock:
            if doc_id not in self._docs:
                return
            self._ensure_seq()
            self._seq += 1
            self._append_wal({"seq": self._seq, "op": "delete",
                              "doc_id": doc_id})
            self._unindex(doc_id)
            self._after_change()

    def _apply_put(self, doc_id, text):
        if doc_id in self._docs:
            self._unindex(doc_id)
        self._docs[doc_id] = text
        for term in tokenize(text):
            self._postings.setdefault(term, set()).add(doc_id)

    def _unindex(self, doc_id):
        text = self._docs.pop(doc_id)
        for term in tokenize(text):
            bucket = self._postings.get(term)
            if bucket:
                bucket.discard(doc_id)
                if not bucket:
                    del self._postings[term]

    # -- 日志 ---------------------------------------------------------
    def _wal_path(self):
        return os.path.join(self._dir, WAL_NAME)

    def _ensure_seq(self):
        """没调 load() 就直接写时，先从快照和日志把 seq 接上。"""
        if self._seq is not None:
            return
        self._seq = 0
        path = os.path.join(self._dir, SNAPSHOT_NAME)
        if os.path.exists(path):
            with open(path) as f:
                self._seq = json.load(f).get("seq", 0)
        for record in self._iter_wal():
            if record["seq"] > self._seq:
                self._seq = record["seq"]

    def _append_wal(self, record):
        if self._wal is None:
            self._wal = open(self._wal_path(), "a")
        self._wal.write(_encode_record(record))
        self._wal.flush()
        os.fsync(self._wal.fileno())

    def _trim_wal(self):
        """快照已覆盖全部日志，整份删除；下次变更时重建。"""
        if self._wal is not None:
            self._wal.close()
            self._wal = None
        try:
            os.remove(self._wal_path())
        except FileNotFoundError:
            pass

    def close(self):
        """关闭 WAL 句柄；已落盘的日志不受影响。"""
        with self._lock:
            if self._wal is not None:
                self._wal.close()
                self._wal = None

    def __del__(self):
        wal = getattr(self, "_wal", None)
        if wal is not None:
            try:
                wal.close()
            except Exception:
                pass

    def _after_change(self):
        self._ops += 1
        if self._ops >= self._snapshot_every:
            self.snapshot()

    # -- 落盘 / 恢复 --------------------------------------------------
    def snapshot(self):
        """整份索引原子写入快照文件，成功后裁剪 WAL。"""
        with self._lock:
            self._ensure_seq()
            payload = {"docs": self._docs, "ops": self._ops, "seq": self._seq}
            fd, tmp = tempfile.mkstemp(dir=self._dir)
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, os.path.join(self._dir, SNAPSHOT_NAME))
            self._ops = 0
            self._trim_wal()
            dir_fd = os.open(self._dir, os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def load(self):
        """从快照重建内存索引，再重放快照之后的日志，返回文档数。"""
        with self._lock:
            path = os.path.join(self._dir, SNAPSHOT_NAME)
            if os.path.exists(path):
                with open(path) as f:
                    payload = json.load(f)
                self._docs = dict(payload["docs"])
                self._seq = payload.get("seq", 0)
            else:
                self._docs = {}
                self._seq = 0
            self._postings = {}
            for doc_id, text in self._docs.items():
                for term in tokenize(text):
                    self._postings.setdefault(term, set()).add(doc_id)
            self._ops = 0
            self._replay_wal()
            return len(self._docs)

    def _replay_wal(self):
        """重放 seq 大于当前位置的日志；遇到坏记录即停，并截掉撕写尾部。"""
        for record in self._iter_wal():
            if record["seq"] <= self._seq:
                continue
            if record["op"] == "put":
                self._apply_put(record["doc_id"], record["text"])
            elif record["doc_id"] in self._docs:
                self._unindex(record["doc_id"])
            self._seq = record["seq"]

    def _iter_wal(self):
        """逐条产出有效日志记录；读完有效前缀后截掉撕写尾部。"""
        path = self._wal_path()
        if not os.path.exists(path):
            return
        good_end = 0
        with open(path) as f:
            while True:
                line = f.readline()
                if not line:
                    break
                record = _decode_record(line)
                if record is None:
                    break
                good_end = f.tell()
                yield record
        if os.path.getsize(path) != good_end:
            with open(path, "r+") as f:
                f.truncate(good_end)
                f.flush()
                os.fsync(f.fileno())
