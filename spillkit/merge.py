"""多路归并：把若干有序 run 文件合成一个有序 run 文件。

每个 run 文件内部按 (key(record), seq) 有序，seq 是记录进入排序器时的
全局序号，同一个 key 在每个 run 里至多出现一次。归并时跨 run 按 key
去重，同 key 只留 seq 最小（最早进入）的那条，输出同样按 (key, seq)
有序。

句柄是硬预算：一趟归并同时打开的输入 run 数至多为 fd_limit - 1，
再加上一个输出文件正好不超过 guard 的 fd_limit。输入 run 更多时由
调用方分多趟归并。
"""

import heapq

from spillkit.runfile import RunReader, write_run

_MISSING = object()


def merge_runs(paths, key, out_path, guard):
    """归并 paths 里的 run 文件，跨 run 去重后写入 out_path。

    每个输入 run 内部按 (key, seq) 有序且 key 唯一；输出按 (key, seq)
    有序，每个 key 只保留 seq 最小的一条。为了不冲破句柄预算，单趟
    最多接受 ``guard.fd_limit - 1`` 个输入，更多输入请分多趟归并。
    返回写出条数。
    """
    fan_in = guard.fd_limit - 1
    if len(paths) > fan_in:
        raise ValueError(
            "单趟归并最多 %d 个输入 run，收到 %d 个，请分多趟归并"
            % (fan_in, len(paths))
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
                    record_key = key(record)
                    heapq.heappush(heap, (record_key, seq, reader, record))
            while heap:
                record_key, seq, reader, record = heapq.heappop(heap)
                item = reader.next()
                if item is not None:
                    next_seq, next_record = item
                    heapq.heappush(
                        heap, (key(next_record), next_seq, reader, next_record)
                    )
                # 堆顶永远是当前 key 下 seq 最小的那条；同一 key 的
                # 其余记录直接丢弃，跨 run 的重复由此收敛成一条。
                if record_key != last_key:
                    yield seq, record
                    last_key = record_key

        return write_run(out_path, stream(), guard)
    finally:
        for reader in readers:
            reader.close()
