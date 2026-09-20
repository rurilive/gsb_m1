"""内存时序库演示。"""
from tsdb import TimeSeriesStore

s = TimeSeriesStore()
s.write_many([(100, 1.5), (200, 2.5), (300, 3.5), (400, 4.5)])
print("span:", s.span(), "count:", len(s))
print("query(150, 350):", s.query(150, 350))

# 第二段：降采样归档演示（留给实现者补）
