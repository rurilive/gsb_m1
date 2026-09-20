"""分片键值表演示。"""
import os
import tempfile

from shardstore import ShardedKV
from shardstore.store import _digest

kv = ShardedKV(["shard-0", "shard-1", "shard-2"])
for i in range(6):
    kv.put("order:%d" % i, i * 10)
print("分片:", kv.shards())
for i in range(6):
    key = "order:%d" % i
    print(key, "->", kv.shard_of(key), "=", kv.get(key))
print("分布:", kv.distribution(), "总计:", kv.total())

# 第二段：在线分裂演示
#
# shard-0 突然涨到别的片好几倍，热点客户的键全挤在它身上。这里不重新
# 取模全量重排，只把 shard-0 沿哈希位劈成 shard-0 / shard-0b，别片不动；
# 中间搬一阵停一阵，并模拟进程重启从断点接着搬。
print("\n== 在线分裂 ==")
state_path = os.path.join(tempfile.mkdtemp(), "split-state.json")
store = ShardedKV(["shard-0", "shard-1", "shard-2"], state_path=state_path)
hot = "shard-0"
keys, i = [], 0
while len(keys) < 600:  # 只挑天然落在 shard-0 的键，模拟单客户挤在同一片
    candidate = "hot-cust:%d" % i
    if store.shard_of(candidate) == hot:
        keys.append(candidate)
        store.put(candidate, i)
    i += 1
for i, key in enumerate(keys):
    store.put(key, i)
print("分裂前分布:", store.distribution())
print("热点片:", hot, "条数:", store.size(hot))

progress = store.begin_split(hot, hot + "b", batch_size=80)
print("开始分裂 %s -> %s/%s，快照 %d 个键，待搬 %d 个"
      % (hot, hot, hot + "b", progress["snapshot_size"], progress["half_total"]))

store.migrate_batch()
store.migrate_batch()
mid = store.split_progress()
print("搬了两批：游标 %d/%d，已搬 %d，剩 %d"
      % (mid["scanned"], mid["snapshot_size"], mid["moved"],
         mid["remaining_snapshot"]))

# 搬运期间热点键还在被反复写：两边都落，读先问新片，没有回退老片
store.put(keys[0], "rewrite-1")
print("迁移中读写热点键:", store.get(keys[0]))

# 进程在这重启过一回：路由和游标从状态文件恢复，搬过的不重搬
store._routing = store._load_state(["shard-0", "shard-1", "shard-2"])
restarted = store.split_progress()
print("重启后从断点继续：游标仍是", restarted["scanned"], "/",
      restarted["snapshot_size"])

store.migrate_until_done()
store.put(keys[0], "rewrite-2")  # 提交前最后一刻的写入，由提交追平兜底
store.commit_split()
print("提交后分布:", store.distribution(), "总计:", store.total())
print("热点键最终值:", store.get(keys[0]), "路由片:", store.shard_of(keys[0]))

# 劈完还能接着劈，片数涨了路由依旧是确定、完整的划分
store.begin_split(hot + "b", hot + "b2", batch_size=80)
store.migrate_until_done()
store.commit_split()
owners = {store.shard_of(key) for key in keys}
print("再次分裂后片集合:", store.shards())
print("热点客户键分布:", {o: sum(1 for k in keys if store.shard_of(k) == o)
                       for o in sorted(owners)})
assert all(store.get(key) is not None for key in keys)
print("全部键可读，总计:", store.total())
