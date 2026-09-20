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

## 批量实现说明

- `batch_acquire(nodes, ttl=None, *, during=None)` 在管理器锁与成员表锁双重临界区内，先校验成员并记下 `generation()` 与节点快照，提交前再比对一次，表被增删或改优先级就抛 `BatchAborted`；非成员抛 `UnknownMember`、ttl 非正抛 `ValueError`，任何失败都整批作废、不留段落，成功时同一时钟读数整批生效
- 原子性边界：仅覆盖“校验—提交”这一临界区；`during` 钩子（测试/演示用）在提交前触发，期间成员表的任何增删都能让本批作废
- `compact(node)` 按起点排序，相邻、重叠或首尾相接（`start <= 上一段到期`）的段落合成一段，到期取各段最晚值，不凭空延长；有间隔的保持独立，过期段同样参与合并不丢弃
- `batch_release(nodes)` 逐节点释放且按入参去重，真正释放的进 `released`、本来就空的进 `empty`、不在表里的进 `unknown`（即 `failures`）；已释放的立即生效不回滚，个别失败不拖停整批
