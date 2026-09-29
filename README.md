# pipeflow

纯标准库的流式数据处理包，无外部依赖。

## 现状

pipeflow/core.py 提供逐条处理的 run_stream：

- run_stream(source, process, sink, initial=None)：把 source 里的记录按序取出，
  逐条经 process 变换后交给 sink 聚合，返回累计结果
- process 抛出的异常一路冒泡并中断处理，之前已交给 sink 的记录保留

tests/test_pipe.py 锁住这些行为。

## 目标

在同一个包里把逐条循环扩成可组合、有背压的批处理管道，新增 Source、Map、
Filter、FlatMap、Batch、Sink 六个算子和把它们串起来的 Pipeline：

- 算子可链式组合，Pipeline 构造接收 source、中间算子与 sink，可调链式方法追加
- 算子之间用有界队列连接，队列写满时上游阻塞等待而非无限堆积，容量可配且非法值 fail fast
- Batch 攒够 batch_size 条或超过 timeout 就冲刷，超时由注入时钟驱动
- 单条处理异常按 skip、retry、abort 三种策略处置，重试有界，异常不被吞掉
- run 结束返回 processed、skipped、failed 计数

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

算子间各有一条有界队列；生产者往满队列写入时在条件变量上等待，消费者取走一条
后唤醒它，因此上游在被阻塞期间不会多读，慢下游的进度反过来压住上游的产出。
每条记录在源头盖上产生时刻并沿队列带到下游，Batch 只用记录自带的到达时刻判定：
一批自第一条起，下一条到达时若间隔已到 timeout，就先把旧批冲出再开新批，判定
只依赖记录的时刻、不依赖线程调度。Batch 攒够 batch_size 立即冲刷，进入的源
结束前用 flush 冲出残留。abort 策略下停止标志点亮全部条件变量，阻塞的上游立刻
收工，原始异常由 run 抛给调用方。