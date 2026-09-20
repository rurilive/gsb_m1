"""布隆过滤器演示。"""
from bloomx import BloomFilter

bf = BloomFilter(capacity=1000, fp_rate=0.01)
for word in ["alpha", "beta", "gamma"]:
    bf.add(word)

print("bits:", bf.num_bits, "hashes:", bf.num_hashes)
print("alpha in bf:", "alpha" in bf)
print("delta in bf:", "delta" in bf)
print("count:", len(bf))

# 第二段：在线扩容演示（不停机添片，旧片原封不动，查询跨所有片）
from bloomx import ShardBloomFilter

sbf = ShardBloomFilter(capacity=1000, fp_rate=0.01)
sbf.add("legacy-event")

sbf.add_shard()  # 数据涨了就添一片，添片期间 add 照常进行
sbf.add("fresh-event")

print("shards:", len(sbf.shards))
print("legacy-event in sbf:", "legacy-event" in sbf)
print("fresh-event in sbf:", "fresh-event" in sbf)
print("overall fp rate: %.4f" % sbf.fp_rate())
sbf.save("/tmp/bloomx_demo.blm2")
print("reloaded shards:", len(ShardBloomFilter.load("/tmp/bloomx_demo.blm2").shards))
