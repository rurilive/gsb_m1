"""布隆过滤器演示。"""
from bloomx import BloomFilter

bf = BloomFilter(capacity=1000, fp_rate=0.01)
for word in ["alpha", "beta", "gamma"]:
    bf.add(word)

print("bits:", bf.num_bits, "hashes:", bf.num_hashes)
print("alpha in bf:", "alpha" in bf)
print("delta in bf:", "delta" in bf)
print("count:", len(bf))

# 第二段：在线扩容演示（留给实现者补）
