# evokit

事件溯源聚合：把领域事件记成有序事件流，再按事件重放出当前状态，纯标准库，无外部依赖。

## 现状

evokit/aggregate.py 提供 Aggregate 与 Event：

- Aggregate(apply=None, initial=None)：apply 是重放函数，缺省 apply_default 支持 set 型事件；initial 是初始状态
- append(etype, data=None)：追加一条事件并立即重放，返回该事件版本（从 1 起）
- replay()：从第 0 条事件开始全量重放，返回状态
- state：最近一次重放得到的状态
- events()：事件流快照，按版本升序，返回副本
- version：当前版本（已追加事件条数）
- Event：version / etype / data，可比较、可哈希
- apply_default(event, state)：按 data 里的 field 与 value 写回状态，无 field 则不动
- 内部一把可重入锁保护读写

## 问题

只有全量重放：每次 replay 都从第 0 条事件重来，事件一多就慢；append 不做版本校验，
并发写入会互相覆盖；重放没有幂等保证；没有快照，也就无从在快照损坏时回退；
事件流只能整体取出，不能按版本区间查询。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_aggregate.py 基线一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
