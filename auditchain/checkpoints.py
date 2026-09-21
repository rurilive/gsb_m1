"""链检查点：每 N 条记录固化一个锚点。

检查点放在日志旁边的旁路文件 ``<日志路径>.ckpt``，一行一条 JSON，
字段固定：

- seq: 锚定的是第几号记录
- digest: 该记录当时算出的摘要
- prev: 该记录的上一条摘要
- offset: 该记录在日志文件里的字节偏移（补链重写后只作信息参考）

巡检从最近一个检查点往下核，不用每次从头算。检查点文件坏一行不拖垮
整个库：读的时候跳过坏行，写的时候追加，缺了的锚点由日志打开时重建。
"""

import os
import threading

from auditchain.codec import RecordError, decode_line, encode_line

SEQ_FIELD = "seq"
DIGEST_FIELD = "digest"
PREV_FIELD = "prev"
OFFSET_FIELD = "offset"


def is_valid_anchor(anchor):
    """锚点结构是否合法，值对不对由核链的人拿日志去比。"""
    if not isinstance(anchor, dict):
        return False
    seq = anchor.get(SEQ_FIELD)
    digest = anchor.get(DIGEST_FIELD)
    prev = anchor.get(PREV_FIELD)
    offset = anchor.get(OFFSET_FIELD)
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
        return False
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    try:
        int(digest, 16)
    except ValueError:
        return False
    if not isinstance(prev, str):
        return False
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return False
    return True


class CheckpointStore:
    """旁路检查点文件的追加、读取与整体重写。"""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()

    def append(self, seq, digest, prev, offset):
        """固化一个检查点，按提交顺序追加。"""
        anchor = {
            SEQ_FIELD: int(seq),
            DIGEST_FIELD: digest,
            PREV_FIELD: prev,
            OFFSET_FIELD: int(offset),
        }
        with self._lock:
            with open(self.path, "ab") as handle:
                handle.write(encode_line(anchor))
                handle.flush()

    def load(self):
        """按文件顺序读回全部合法锚点，坏行跳过，文件不存在返回空。"""
        try:
            with open(self.path, "rb") as handle:
                data = handle.read()
        except FileNotFoundError:
            return []

        anchors = []
        for raw in data.splitlines():
            if not raw.strip():
                continue
            try:
                anchor = decode_line(raw)
            except RecordError:
                continue
            if is_valid_anchor(anchor):
                anchors.append(anchor)
        return anchors

    def rewrite(self, anchors):
        """整体重写检查点文件（补链后重建用）。文件不存在且无内容时不建。"""
        anchors = [anchor for anchor in anchors if is_valid_anchor(anchor)]
        with self._lock:
            if not anchors:
                if os.path.exists(self.path):
                    os.remove(self.path)
                return
            blob = b"".join(encode_line(anchor) for anchor in anchors)
            tmp_path = "%s.tmp%d" % (self.path, os.getpid())
            try:
                with open(tmp_path, "wb") as handle:
                    handle.write(blob)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, self.path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    def exists(self):
        return os.path.exists(self.path)
