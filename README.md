# crdtbox

离线优先应用的副本状态库，纯标准库，无外部依赖。副本各自离线改数据，联网时把状态合到一起。

## 现状

`crdtbox/counter.py` 提供多槽位只增计数器 `GCounter`：

- `GCounter(replica_id)`：副本标识为非空字符串
- `incr(key, n=1)`：给槽位 `key` 加 `n`，`n` 必须为正整数
- `value()`：所有槽位计数之和
- `merge(other)`：就地并入另一副本，同槽位取较大值，返回自身

`crdtbox/set.py` 提供带移除的集合 `TwoPhaseSet`：

- `add(item)` / `discard(item)`：加入与移除，都返回自身
- `contains(item)` / `value()`：`value()` 返回升序元组
- `merge(other)`：加入集与移除集分别取并集，返回自身

两个类都没有锁，单副本单线程使用。

## 问题

集合的移除集只增不减，元素删掉之后再想加回来永远加不回来；墓碑长期堆在内存里没有回收的路子；副本状态只能整对象传递，落盘和跨进程都不方便。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_counter.py`、`tests/test_set.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 计数器与集合的现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

`crdtbox/orset.py` 的 `ORSet` 是添加胜出的观测移除集：每次加入打唯一点 `(replica_id, 序号)`，删除把观测到的点记为墓碑，并存删除时刻的版本向量快照作为因果上下文；合并用对方时钟与墓碑过滤点，交换律、结合律、幂等成立，并发加入压过删除。

各副本经合并互播 `_known`（每个副本见过的时钟），`gc()` 只回收上下文被所有已知副本时钟覆盖的墓碑；回收后旧状态里残存的点会被本地时钟判为"见过却无人持有"而丢弃，已删元素不会复活。

`to_dict()`/`from_dict()` 把时钟、加入点、墓碑、`_known` 编码为纯标准数据类型（可直接 `json.dumps` 落盘或跨进程传输），往返不丢信息。
