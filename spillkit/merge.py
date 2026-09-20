"""多路归并：把若干有序 run 文件合成一个有序且按 key 去重的 run 文件。

每个 run 文件内部按 (key(record), seq) 有序，且同一个 key 在单个 run
里至多出现一次；seq 是记录进入排序器时的全局序号。归并输出同样按
(key, seq) 有序，同一个 key 分布在多个 run 里时只保留 seq 最小
（最早进入）的那一条。
"""

import heapq

from spillkit.runfile import RunReader, TooManyOpenRuns, write_run

_MISSING = object()


def merge_runs(paths, key, out_path, guard):
    """归并 paths 里的全部 run 文件，去重后写入 out_path，返回写出条数。

    每个输入 reader 占一个句柄、写出占一个句柄，同时打开数为
    len(paths) + 1，调用方需保证不超过 guard.fd_limit。
    """
    if len(paths) + 1 > guard.fd_limit:
        raise TooManyOpenRuns(
            "一次归并 %d 个 run 需要 %d 个句柄，超过上限 %d"
            % (len(paths), len(paths) + 1, guard.fd_limit)
        )
    readers = [RunReader(path, guard) for path in paths]
    try:

        def stream():
            heap = []
            last_key = _MISSING
            for reader in readers:
                item = reader.next()
                if item is not None:
                    seq, record = item
                    heapq.heappush(heap, (key(record), seq, reader, record))
            while heap:
                record_key, seq, reader, record = heapq.heappop(heap)
                item = reader.next()
                if item is not None:
                    next_seq, next_record = item
                    heapq.heappush(
                        heap, (key(next_record), next_seq, reader, next_record)
                    )
                if record_key != last_key:
                    yield seq, record
                    last_key = record_key

        return write_run(out_path, stream(), guard)
    finally:
        for reader in readers:
            reader.close()
