"""分片键值表演示。"""
from shardstore import ShardedKV

kv = ShardedKV(["shard-0", "shard-1", "shard-2"])
for i in range(6):
    kv.put("order:%d" % i, i * 10)
print("分片:", kv.shards())
for i in range(6):
    key = "order:%d" % i
    print(key, "->", kv.shard_of(key), "=", kv.get(key))
print("分布:", kv.distribution(), "总计:", kv.total())

# 第二段：在线分裂演示（留给实现者补）
