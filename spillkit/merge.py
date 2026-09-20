"""多路归并：把若干有序 run 文件合成一个有序 run 文件。

每个 run 文件内部按 (key(record), seq) 有序，seq 是记录进入排序器时的
全局序号。归并输出同样按 (key, seq) 有序。
"""

import heapq

from spillkit.runfile import RunReader, write_run


def merge_runs(paths, key, out_path, guard):
    """归并 paths 里的全部 run 文件，写入 out_path，返回写出条数。"""
    readers = [RunReader(path, guard) for path in paths]
    try:
        def stream():
            heap = []
            for reader in readers:
                item = reader.next()
                if item is not None:
                    seq, record = item
                    heapq.heappush(heap, (key(record), seq, reader, record))
            while heap:
                _, seq, reader, record = heapq.heappop(heap)
                item = reader.next()
                if item is not None:
                    next_seq, next_record = item
                    heapq.heappush(
                        heap, (key(next_record), next_seq, reader, next_record)
                    )
                yield seq, record

        return write_run(out_path, stream(), guard)
    finally:
        for reader in readers:
            reader.close()
