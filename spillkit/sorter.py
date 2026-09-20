"""外部排序去重器：缓冲区装满就排序落盘，最后归并全部 run。

内存里只剩一份大小受 memory_limit 限制的缓冲；记录编码、run 读写
见 spillkit/runfile.py，多路归并见 spillkit/merge.py。
"""

import os
import shutil
import tempfile

from spillkit.merge import merge_runs
from spillkit.runfile import RunFileGuard, RunReader, remove_file, write_run

_MISSING = object()


def default_key(record):
    """默认取第一个制表符之前的内容当排序键。"""
    return record.split("\t", 1)[0]


class SortDeduper:
    """边收边落盘的排序去重器。

    用法：反复调用 add(record) 喂记录，最后 finish() 拿到排好序、
    每个 key 只留最早一条的结果列表，用完 close() 清理临时文件。

    workdir：溢写目录，默认新建临时目录并在 close() 时整体删掉。
    memory_limit：内存里最多攒多少条记录，装满即落盘。
    fd_limit：同时打开的 run 文件数上限（含归并中间输出）。
    key：从记录里取排序键的函数，默认见 default_key。
    """

    def __init__(self, workdir=None, memory_limit=4096, fd_limit=8, key=None):
        if memory_limit < 1:
            raise ValueError("memory_limit 至少为 1")
        self._key = key if key is not None else default_key
        self._limit = memory_limit
        self._guard = RunFileGuard(fd_limit)
        self._owns_dir = workdir is None
        self._dir = workdir if workdir is not None else tempfile.mkdtemp(
            prefix="spillkit-"
        )
        os.makedirs(self._dir, exist_ok=True)
        self._buf = []
        self._seq = 0
        self._runs = []
        self._created = []
        self._finished = False
        self._stats = {
            "records_in": 0,
            "runs_written": 0,
            "merge_passes": 0,
            "peak_buffered": 0,
            "peak_open_runs": 0,
        }

    # -- 写入 ------------------------------------------------------------

    def add(self, record):
        """收一条记录，缓冲满了就落盘。"""
        if self._finished:
            raise RuntimeError("finish 之后不能再 add")
        self._seq += 1
        self._buf.append((self._seq, record))
        self._stats["records_in"] = self._seq
        if len(self._buf) > self._stats["peak_buffered"]:
            self._stats["peak_buffered"] = len(self._buf)
        if len(self._buf) >= self._limit:
            self._spill()

    def _spill(self):
        """把当前缓冲区排序去重后写成一个 run 文件。"""
        if not self._buf:
            return
        path = self._run_path(len(self._runs))
        write_run(path, self._sorted_dedup(self._buf), self._guard)
        self._runs.append(path)
        self._created.append(path)
        self._stats["runs_written"] += 1
        self._buf = []

    def _sorted_dedup(self, entries):
        """按 (key, seq) 排序，同一个 key 只留最早进来的那条。"""
        ordered = sorted(entries, key=lambda item: (self._key(item[1]), item[0]))
        out = []
        last_key = _MISSING
        for seq, record in ordered:
            record_key = self._key(record)
            if record_key == last_key:
                continue
            out.append((seq, record))
            last_key = record_key
        return out

    def _run_path(self, index):
        return os.path.join(self._dir, "run-%05d.run" % index)

    # -- 收尾 ------------------------------------------------------------

    def finish(self):
        """返回排好序、按 key 去重后的记录列表。"""
        self._finished = True
        if not self._runs:
            return [record for _, record in self._sorted_dedup(self._buf)]
        final_path = os.path.join(self._dir, "merged-00000.run")
        self._created.append(final_path)
        self._stats["merge_passes"] += 1
        merge_runs(self._runs, self._key, final_path, self._guard)
        out = []
        reader = RunReader(final_path, self._guard)
        try:
            while True:
                item = reader.next()
                if item is None:
                    break
                out.append(item[1])
        finally:
            reader.close()
        self._stats["peak_open_runs"] = self._guard.peak
        return out

    def close(self):
        """删掉这次排序产生的全部 run 文件和临时目录。"""
        for path in self._created:
            remove_file(path)
        self._created = []
        self._runs = []
        if self._owns_dir and os.path.isdir(self._dir):
            shutil.rmtree(self._dir, ignore_errors=True)

    def stats(self):
        """运行期计数：records_in / runs_written / merge_passes /
        peak_buffered / peak_open_runs。"""
        self._stats["peak_open_runs"] = self._guard.peak
        return dict(self._stats)


def sort_dedup(records, workdir=None, memory_limit=4096, fd_limit=8, key=None):
    """便利函数：喂完一批记录直接拿结果，用完即清理。"""
    sorter = SortDeduper(
        workdir=workdir, memory_limit=memory_limit, fd_limit=fd_limit, key=key
    )
    try:
        for record in records:
            sorter.add(record)
        return sorter.finish()
    finally:
        sorter.close()
