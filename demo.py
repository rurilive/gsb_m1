"""倒排索引演示：写入、检索、落盘、重载。"""
import json
import os
import shutil
import tempfile
import zlib

from idxstore import IndexStore, WAL_NAME

workdir = tempfile.mkdtemp(prefix="idxstore-demo-")
try:
    store = IndexStore(workdir, snapshot_every=10)
    store.put("d1", "the quick brown fox")
    store.put("d2", "quick silver fox")
    store.put("d3", "lazy brown dog")

    print("search(fox)   ->", store.search("fox"))
    print("search(brown) ->", store.search("brown"))
    print("get(d2)       ->", store.get("d2"))

    store.delete("d1")
    print("after delete, search(fox) ->", store.search("fox"))

    store.snapshot()
    reopened = IndexStore(workdir)
    print("reloaded docs ->", reopened.load())
    print("reloaded search(fox) ->", reopened.search("fox"))

    # 第二段：进程被 kill 后从日志增量恢复（没来得及快照也不丢）
    wal_dir = tempfile.mkdtemp(prefix="idxstore-wal-demo-")
    try:
        killed = IndexStore(wal_dir, snapshot_every=1000)
        killed.put("n1", "wal keeps every change safe")
        killed.put("n2", "no snapshot needed before crash")
        killed.delete("n1")
        # 进程在攒够快照次数之前被 kill -9：内存没了，日志已落盘。
        killed.close()

        recovered = IndexStore(wal_dir, snapshot_every=1000)
        print("recovered from WAL, docs ->", recovered.load())
        print("recovered search(safe) ->", recovered.search("safe"))
        print("recovered search(snapshot) ->", recovered.search("snapshot"))

        # 更狠的情况：掉电时最后一条日志只写了一半，重启不应抛异常。
        payload = json.dumps(["put", "n3", "torn by power loss"]).encode("utf-8")
        head = b"%d:%08x:" % (len(payload), zlib.crc32(payload) & 0xFFFFFFFF)
        with open(os.path.join(wal_dir, WAL_NAME), "ab") as f:
            f.write(head + payload[:6])

        after_power_loss = IndexStore(wal_dir, snapshot_every=1000)
        print("after torn tail, docs ->", after_power_loss.load())
        after_power_loss.put("n4", "life goes on")
        print("search(life) ->", after_power_loss.search("life"))
        after_power_loss.close()
    finally:
        shutil.rmtree(wal_dir, ignore_errors=True)
finally:
    shutil.rmtree(workdir, ignore_errors=True)
