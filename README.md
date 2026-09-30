# morollback

区间统计工具包，纯标准库，无外部依赖。给一个值序列与一批询问区间，离线回答
区间内不同值个数、众数、最大频率、指定值出现次数与极差。

## 现状

朴素实现，能算对但规模一大就慢。

- `morollback/naive.py`：`normalize_queries()` 把询问规整成二元区间（空区间规范为
  左端点大于右端点），`prepare()` 返回记录对象，`collapsed_intervals()` 把区间
  按左端点升序压平，`scan_steps()` 暴露逐询问扫描步数；`IntervalStats` 每个询问都
  用切片把区间内的值重新取出来再统计，`query_distinct()` 求不同值个数，
  `query_mode()` 求众数（并列取最小），`query_maxfreq()` 求众数频率，
  `query_count()` 求某值出现次数，`query_range()` 求极差，`answer()` 汇总一条询问，
  `run()` 对一批询问逐条回答并给出总核对值；异常基类 `Erro` 与两个子类也在本文件。

单条询问与区间长度成正比，同一段区间被反复重扫；询问一多，总代价就是询问条数乘
区间长度的量级。

## 问题

没有把询问按端点排序来批量维护，每个询问都从零重扫一遍；可加的统计与难以删除的
统计混在同一条重扫路上，没有可对照的规模指标，慢在哪看不出来。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
