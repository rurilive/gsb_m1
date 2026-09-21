"""段落后端：段 blob 与一份 meta 文档的落盘口子。

这里给的是进程内字典实现，真机部署换成文件或对象存储实现即可，
接口不动。读出去的都是副本，调用方改了不会串回后端。
"""

import copy


class MemoryBackend:
    """进程内的段落后端。"""

    def __init__(self):
        self.blobs = {}
        self.meta = None

    def segment_ids(self):
        """后端里现存的段 id，升序。"""
        return sorted(self.blobs)

    def read_segment(self, sid):
        """读一段的键值对，返回副本。"""
        if sid not in self.blobs:
            raise KeyError(sid)
        return list(self.blobs[sid])

    def write_segment(self, sid, pairs):
        """覆盖写一段。"""
        self.blobs[sid] = [tuple(kv) for kv in pairs]

    def drop_segment(self, sid):
        """删掉一段，本来就不在也算成功。"""
        self.blobs.pop(sid, None)

    def load_meta(self):
        """读 meta 文档，还没有就返回 None。"""
        return None if self.meta is None else copy.deepcopy(self.meta)

    def save_meta(self, meta):
        """覆盖写 meta 文档。"""
        self.meta = copy.deepcopy(meta)

    def __repr__(self):
        return "MemoryBackend(segments=%r, has_meta=%s)" % (
            self.segment_ids(),
            self.meta is not None,
        )
