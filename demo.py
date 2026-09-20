"""内存时序库演示。"""
from tsdb import RollupStore, TimeSeriesStore

s = TimeSeriesStore()
s.write_many([(100, 1.5), (200, 2.5), (300, 3.5), (400, 4.5)])
print("span:", s.span(), "count:", len(s))
print("query(150, 350):", s.query(150, 350))

# 第二段：降采样归档演示
r = RollupStore(resolutions=(60, 3600))
r.write_many([(t, 1.0) for t in range(0, 7200, 10)])
print("归档前原始点:", len(r))
r.archive(3600)
print("归档后原始点:", len(r))
r.write(100, 5.0)  # 迟到点：直接并入已归档窗口，不丢
r.archive(3600)    # 重跑归档：幂等，均值不会翻倍
hour = r.query(0, 3599)
print("大范围查询走 60s 层:", len(hour), "个桶, 首个桶:", hour[0])
print("小范围查询走原始点:", r.query(3600, 3630))
