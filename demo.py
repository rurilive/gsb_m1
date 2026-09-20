"""布隆过滤器演示。"""
import os
import tempfile

from bloomx import BloomFilter, ShardedBloomFilter

bf = BloomFilter(capacity=1000, fp_rate=0.01)
for word in ["alpha", "beta", "gamma"]:
    bf.add(word)

print("bits:", bf.num_bits, "hashes:", bf.num_hashes)
print("alpha in bf:", "alpha" in bf)
print("delta in bf:", "delta" in bf)
print("count:", len(bf))

# 第二段：在线扩容演示（留给实现者补）
sharded = ShardedBloomFilter(shard_capacity=200, fp_rate=0.01, max_shards=8)
for i in range(200):
    sharded.add("evt-%d" % i)  # 写满当前片会自动追加新片，服务不中断
sharded.add_shard()  # 也可以按业务节奏在线手动添片
sharded.add("evt-fresh")

print("shards:", sharded.num_shards, "count:", len(sharded))
print("evt-0 across shards:", "evt-0" in sharded)
print("evt-fresh across shards:", "evt-fresh" in sharded)
print("overall fp rate: %.4f%%" % (sharded.fp_rate_overall * 100))

# 老版本单实例（BLM1）文件也能直接读回，之后照常在线扩容
state_path = os.path.join(tempfile.mkdtemp(), "bloom.bin")
with open(state_path, "wb") as handle:
    handle.write(bf.to_bytes())
restored = ShardedBloomFilter.load(state_path)
print("legacy loaded, alpha in sharded:", "alpha" in restored)
restored.add_shard()
restored.save(state_path)
print("state saved in new format:", restored.num_shards, "shards")
