"""批量任务并发执行：固定线程分片处理，单条失败不拖垮整批。"""

import threading


class ItemFailure(Exception):
    """map_batch 结果里的失败占位，携带原始条目与异常。"""

    def __init__(self, item, error):
        super().__init__("item failed: {!r}".format(item))
        self.item = item
        self.error = error


def _split(items, parts):
    """把 items 连续切成 parts 片，前面的片多承担余数。"""
    base, extra = divmod(len(items), parts)
    out = []
    start = 0
    for i in range(parts):
        size = base + (1 if i < extra else 0)
        out.append((start, items[start:start + size]))
        start += size
    return out


def map_batch(fn, items, workers=4):
    """用 workers 个线程并发处理 items，返回与 items 等长的结果列表。

    fn(item) 的返回值按原顺序放回；fn 抛异常时对应位置放
    ItemFailure(item, exc)，其余条目照常处理。workers 小于 1 视为 1。
    """
    items = list(items)
    if not items:
        return []
    workers = max(1, int(workers))
    chunks = _split(items, min(workers, len(items)))
    results = [None] * len(items)
    threads = []
    for start, chunk in chunks:
        t = threading.Thread(target=_run_chunk, args=(fn, chunk, start, results))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results


def _run_chunk(fn, chunk, start, results):
    for i, item in enumerate(chunk):
        try:
            results[start + i] = fn(item)
        except Exception as exc:  # 单条失败兜底，整批继续
            results[start + i] = ItemFailure(item, exc)


def first_failure(results):
    """返回结果列表里第一个 ItemFailure，没有则返回 None。"""
    for r in results:
        if isinstance(r, ItemFailure):
            return r
    return None
