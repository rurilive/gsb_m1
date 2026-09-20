"""内存时序库演示。"""
from tsdb import TimeSeriesStore

s = TimeSeriesStore()
s.write_many([(100, 1.5), (200, 2.5), (300, 3.5), (400, 4.5)])
print("span:", s.span(), "count:", len(s))
print("query(150, 350):", s.query(150, 350))

# 第二段：降采样归档演示
r = TimeSeriesStore(window=60)
# 模拟一整分钟的原始点，另有一个时钟偏慢的迟到点
r.write_many([(t, float(t % 7)) for t in range(0, 180, 5)])
r.archive(before=120)          # 归档窗口 [0,60) 和 [60,120)，原始点随之删除
print("archive 后原始点数:", len(r), "归档窗口:", r.query_rollup(0, 300))
r.write(30, 6.0)               # 迟到点：窗口 [0,60) 已归档才到
r.archive(before=120)          # 重跑幂等：只并入迟到点，不重复计数
print("迟到点并入后:", r.query_rollup(0, 60))
print("query_auto(0, 300) 走归档层:", r.query_auto(0, 300))
print("query_auto(120, 130) 走原始层:", r.query_auto(120, 130))
