"""倒排索引演示：写入、检索、落盘、重载、崩溃后日志恢复。"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

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
    worker = textwrap.dedent("""
        import os, sys
        from idxstore import IndexStore
        s = IndexStore(sys.argv[1])
        s.load()
        s.put("d4", "fox jumps over the dog")
        s.put("d5", "silver fox runs away")
        s.delete("d2")
        os._exit(1)  # 模拟被 kill：不 snapshot，不清场，直接死
    """)
    repo = os.path.dirname(os.path.abspath(__file__))
    subprocess.run([sys.executable, "-c", worker, workdir], cwd=repo)

    recovered = IndexStore(workdir)
    print("recovered docs ->", recovered.load())
    print("recovered search(fox) ->", recovered.search("fox"))
    print("recovered get(d2) ->", recovered.get("d2"))
finally:
    shutil.rmtree(workdir, ignore_errors=True)
