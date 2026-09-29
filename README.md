# pagekit

请求页号驱动的页替换模拟器，纯标准库，无外部依赖。把一串页号喂进去，
看哪些命中、哪些缺失、容量满了挤掉谁。

## 现状

pagekit/simulator.py 提供 PageSimulator：

- PageSimulator(capacity)：按常驻帧数上限建模拟器
- access(page)：请求一个页号，命中返回 True，缺失返回 False
- write(page)：带写的请求，命中把该页标脏，缺失时装入后标脏
- resident()：当前常驻页号，按最近使用次序从早到晚
- stats()：容量、常驻页数、命中、缺失与淘汰数
- hit_ratio()：命中数除以命中数加缺失数
- len() / in：常驻页数与成员判断

淘汰挑最久未访问的常驻页。

## 问题

只记单次访问，扫一遍就走的页和反复回来的页一样受待见；脏页被淘汰时
直接丢掉，写回代价没算进指标；连续的多次写不做合并，一笔一笔都算成
独立写；也没有预取，取回的数据能不能用上无从得知；指标口径只有命中
率一个。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_simulator.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```