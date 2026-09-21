"""只追加的发放日志：记号、租约与幂等请求靠它跨重启活下来。

每条记录是一个 dict，三种事件：

- grant：发放成功，带租约全字段与客户端请求标识 request_id
- deny：带 request_id 的发放撞上活租约被拒，让重放在重启后仍是撞车
- release：归还，带 lease_id

发放/归还先落日志、fsync 完再改内存状态，进程崩在半路最多丢最后一条
没刷盘的，不会出现“内存里发了、盘上没有”。续期不进日志：续期高峰每
秒一万次，路径不许碰磁盘；崩溃后按发号时的原始到期时刻判定活没活，
本来就在 TTL 窗口边缘的租约宁可提前回收，同一资源也不会冒出两份活。

MemoryJournal 不落盘，用来对拍和测试“崩了但日志还在”的重启；
FileJournal 追加写 JSON Lines，每条 fsync，replay 顺序读回全部事件。
"""

import json
import os
import threading
import copy


class MemoryJournal:
    """内存里的只追加日志，线程安全；close 后不能再写。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._records = []
        self._closed = False

    def append(self, record):
        """顺序追加一条记录，返回它的日志序号（从 0 起）。"""
        with self._lock:
            if self._closed:
                raise RuntimeError("journal closed")
            self._records.append(copy.deepcopy(record))
            return len(self._records) - 1

    def replay(self):
        """按写入顺序返回全部记录的副本。"""
        with self._lock:
            return copy.deepcopy(self._records)

    def close(self):
        self._closed = True


class FileJournal:
    """JSON Lines 追加日志，每条 append 都 flush + fsync。"""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        # 先扫一遍：崩溃在写一半会留下截断残行，残行不算提交，截掉。
        self._count = len(self._read_valid())
        self._file = open(path, "a", encoding="utf-8")

    def append(self, record):
        """落一条记录并 fsync，返回它的日志序号（从 0 起）。"""
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            if self._file is None:
                raise RuntimeError("journal closed")
            self._file.write(line + "\n")
            self._file.flush()
            os.fsync(self._file.fileno())
            seq = self._count
            self._count += 1
            return seq

    def replay(self):
        """从头顺序读回全部记录，跳过空行。"""
        return self._read_valid()

    def _read_valid(self):
        records = []
        with open(self.path, "a+b") as source:
            source.seek(0)
            raw = source.read().decode("utf-8")
        lines = raw.split("\n")
        torn = ""
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError:
                # 只有最后一条可能是崩在写一半的残行；中间行坏掉才是真损坏。
                if index != len(lines) - 1:
                    raise
                torn = line
        if torn:
            with open(self.path, "r+b") as source:
                source.seek(0, os.SEEK_END)
                size = source.tell() - len(torn.encode("utf-8"))
                source.truncate(size)
        return records

    def close(self):
        with self._lock:
            if self._file is not None:
                self._file.flush()
                os.fsync(self._file.fileno())
                self._file.close()
                self._file = None
