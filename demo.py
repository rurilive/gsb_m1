"""布隆过滤器演示：第一段定容单实例，第二段在线分片扩容。"""
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

# 第二段：在线扩容演示
# 单片容量定死，写满自动挂新片，旧片冻结、查询问遍所有片。
sbf = ShardedBloomFilter(capacity=100, fp_rate=0.01, max_shards=8)
for i in range(250):
    sbf.add("evt-%d" % i)

print("shards:", sbf.num_shards, "count:", len(sbf))
print("evt-0 in sbf (旧片):", "evt-0" in sbf)
print("evt-249 in sbf (新片):", "evt-249" in sbf)
print("overall fp_rate: %.4f" % sbf.fp_rate)

# 添片不用停机：显式 add_shard() 立刻生效，进行中的写入一条不丢。
sbf.add_shard()
sbf.add("evt-live")
print("after add_shard, shards:", sbf.num_shards,
      "evt-live in sbf:", "evt-live" in sbf)

# 进程重启前 save()，重启后 load() 读回；老版本 BLM1 文件也认。
state_dir = tempfile.mkdtemp(prefix="bloomx-")
state_path = os.path.join(state_dir, "state.bin")
sbf.save(state_path)
restored = ShardedBloomFilter.load(state_path)
print("restored shards:", restored.num_shards,
      "evt-0 in restored:", "evt-0" in restored)
legacy_path = os.path.join(state_dir, "legacy.bin")
with open(legacy_path, "wb") as fh:
    fh.write(bf.to_bytes())
migrated = ShardedBloomFilter.load(legacy_path)
print("legacy BLM1 loaded, alpha in migrated:", "alpha" in migrated)
