# batchlease

选主后发放与回收租约的进程内实现，纯标准库，无外部依赖。

## 现状

`batchlease/lease.py` 里有两块东西：

- `MemberTable`：成员表，节点名到优先级。`add` / `remove` 每次有效变更让 `generation()` 加一，初始成员算第 0 代
- `LeaseManager(members=None, clock=time.monotonic, default_ttl=30.0)`：
  - `primary()` 选主，优先级最高者胜出，同优先级取名字最小的，空表返回 None
  - `acquire(node, ttl=None)` 为节点追加一段租约，返回到期时刻；同一节点可以先后持有多段
  - `renew(node)` 把最后一段从当前时刻起续期；那段已过期或从未申请过都会抛 `NoLease`
  - `release(node)` 清掉节点的全部租约，返回之前是否持有
  - `segments(node)` / `expires_at(node)`（各段里最晚的到期时刻）/ `held(node)`
  - 非成员一律抛 `UnknownMember`，ttl 不为正抛 `ValueError`
- 内部一把锁保护，多线程单操作安全；时间全部来自注入的 clock

## 问题

扩容后要一次给一组节点发租约，逐个申请遇到中途失败会留下半截状态；同一节点反复申请攒下的相邻段落也越滚越多，回收时逐个释放有一两个失败就整批停了。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_lease.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                            # 选主、发租约与回收演示
python3 -m unittest discover -s tests -v   # 行为基线测试
```

## 实现说明

- `acquire_batch(nodes, ttl=None)`：读钟前后两次比对 `generation()`，中途成员表被增删或任何节点非成员、ttl 非法、节点重复，都不落任何一段，已写入的会回滚，抛 `MembershipChanged`。
- 原子性边界：整批评判、写入、复核都在管理器同一把锁内；成员表变更以代数为准，开批前已落定的变更不影响本批。
- `merge(node)`：段落按起点排序，下一段起点 `<=` 当前段到期（首尾相接也算）即并入，合并段到期取各段最晚值，有间隔的不并，到期时刻不会变长。
- `release_batch(nodes)`：逐节点释放不互相拖停，结果用 `BatchReleaseResult` 分记 `released` / `empty`（在表但本来空）/ `unknown`（非成员）。
- 已成功的释放不随后续失败回滚；重复节点只计一次；以上新方法均复用注入 clock 与现有锁，基线方法行为不变。
