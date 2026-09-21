"""分片键值表演示。"""
import os
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

# 第二段：在线分裂演示
state_path = os.path.join(tempfile.mkdtemp(), "split.state")
hot = ShardedKV(["shard-0", "shard-1", "shard-2"], state_path=state_path)
for i in range(300):
    hot.put("user:%d" % i, i)
before = hot.distribution()
print("分裂前:", before, "总计:", hot.total())

fullest = max(before, key=before.get)
child = fullest + "-b"
hot.begin_split(fullest, child)
print("开始分裂:", fullest, "->", child)
while True:
    prog = hot.split_progress()
    print("进度: 已搬 %d / 剩 %d" % (prog["moved"], prog["remaining"]))
    if prog["remaining"] == 0:
        break
    hot.migrate_some(20)
    hot.put("user:7", 777)  # 搬迁期间热点写，双写两片不落空
hot.commit_split()

after = hot.distribution()
print("分裂后:", after, "总计:", hot.total())
print("user:7 =", hot.get("user:7"), "落在", hot.shard_of("user:7"))
untouched = [s for s in before if s != fullest]
print("别片一个键不动:", all(before[s] == after[s] for s in untouched))
