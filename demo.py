"""布隆过滤器演示。"""
import os
import tempfile

from bloomx import BloomFilter, ScalableBloomFilter

bf = BloomFilter(capacity=1000, fp_rate=0.01)
for word in ["alpha", "beta", "gamma"]:
    bf.add(word)

print("bits:", bf.num_bits, "hashes:", bf.num_hashes)
print("alpha in bf:", "alpha" in bf)
print("delta in bf:", "delta" in bf)
print("count:", len(bf))

# 第二段：在线扩容演示
sbf = ScalableBloomFilter(initial_capacity=1000, fp_rate=0.01)
for i in range(5000):
    sbf.add("event-%d" % i)

print("shards:", sbf.shard_count)
print("count:", len(sbf))
print("overall fp rate: %.5f" % sbf.overall_fp_rate)
print("event-42 in sbf:", "event-42" in sbf)

path = os.path.join(tempfile.gettempdir(), "bloomx-demo.bin")
with open(path, "wb") as fh:
    fh.write(sbf.to_bytes())
with open(path, "rb") as fh:
    restored = ScalableBloomFilter.from_bytes(fh.read())
print("after restart, event-42 in sbf:", "event-42" in restored)
