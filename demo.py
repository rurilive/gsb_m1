"""倒排索引演示：写入、检索、落盘、重载。"""
import shutil
import tempfile

from idxstore import IndexStore

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

    # 第二段：进程被 kill 后从日志增量恢复（留给实现者补）
finally:
    shutil.rmtree(workdir, ignore_errors=True)
