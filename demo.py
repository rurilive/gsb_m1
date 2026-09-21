"""分片键值表演示。"""
import shutil
import tempfile

from shardstore import ShardedKV

kv = ShardedKV(["shard-0", "shard-1", "shard-2"])
for i in range(6):
    kv.put("order:%d" % i, i * 10)
print("分片:", kv.shards())
for i in range(6):
    key = "order:%d" % i
    print(key, "->", kv.shard_of(key), "=", kv.get(key))
print("分布:", kv.distribution(), "总计:", kv.total())

# ---------------------------------------------------------------
# 第二段：在线分裂演示（一个客户的键全挤在 shard-0，就地劈成两片）
# ---------------------------------------------------------------
state_dir = tempfile.mkdtemp(prefix="shardstore-demo-")
try:
    store = ShardedKV(["shard-0", "shard-1", "shard-2"], state_dir=state_dir)
    for i in range(60):
        store.put("tenant-a:order:%d" % i, i)
    print("\n分裂前分布:", store.distribution())

    split = store.begin_split("shard-0", "shard-0b")
    keys = store.keys_in("shard-0")
    movers = [k for k in keys if split.is_mover(k)]
    print("shard-0 共 %d 键，对半分：%d 键搬去 shard-0b"
          % (len(keys), len(movers)))

    # 搬的过程中线上读写没停：待搬键写两边，读先问新片再回老片。
    hot = movers[0]
    store.put(hot, "迁移中也在写")
    print("迁移中读热点键:", store.get(hot), "（路由仍是",
          store.shard_of(hot), "）")

    split.migrate(10)
    progress = split.progress()
    print("搬了一批后进度: 已搬 %d / 共 %d，还剩 %d，完成 %.0f%%"
          % (progress["moved"], progress["total"], progress["remaining"],
             progress["fraction"] * 100))

    # 模拟进程在搬一半时重启：检查点 + WAL 让它从断点接着搬。
    moved_so_far = progress["moved"]
    del store, split
    store = ShardedKV.open(state_dir)
    split = store.active_split()
    print("重启后续传：已搬 %d（不从头再来），还剩 %d"
          % (split.progress()["moved"], split.progress()["remaining"]))
    assert split.progress()["moved"] == moved_so_far

    split.drain()
    print("搬完时进度:", {k: v for k, v in split.progress().items()
                         if k != "fraction"})
    new_shard = split.commit()
    print("指针已一次性钉死，新片转正:", new_shard)
    print("分裂后分布:", store.distribution(), "总计:", store.total())
    print("热点键归属:", store.shard_of(hot), "值:", store.get(hot))

    # 劈完这片接着劈：片数涨了，路由照样精确，别片一个键不动。
    split = store.begin_split("shard-0b", "shard-0c")
    split.drain()
    split.commit()
    split = store.begin_split("shard-1", "shard-1b")
    split.drain()
    split.commit()
    print("连续再劈两片后:", store.shards())
    print("最终分布:", store.distribution(), "总计:", store.total())
    assert store.total() == 60
    for i in range(60):
        key = "tenant-a:order:%d" % i
        expected = "迁移中也在写" if key == hot else i
        assert store.get(key) == expected
    print("60 个键全部读得到、归属唯一，演示通过")
    store.close()
finally:
    shutil.rmtree(state_dir, ignore_errors=True)
