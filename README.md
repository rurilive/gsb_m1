# idemkey

支付链路的幂等键存储：按幂等键记住已处理请求的结果，同一个键再提交时
回放上次的结果，避免重复扣款。纯标准库，无外部依赖。

## 模块说明

`idemkey/store.py` 提供 `IdempotencyStore(ttl=None, clock=time.monotonic,
path=None, max_result_size=None)`：

- `begin(key)`：提交前问这个键要不要干活。返回 `True` 表示该由本次请求
  处理；返回 `False` 表示这个键已经处理过，调用方改用 `get(key)` 回放结果
- `finish(key, result)`：把处理结果记到键上，这个键之后就算已处理
- `get(key)`：取这个键已记下的结果，没有就返回 `None`
- `rollback(key)`：处理中途失败时放开 `begin` 占下的键，已 `finish` 的
  记录不会被回滚；返回是否真的放开了一个未完成占位
- `renew(key, ttl=None)`：给有效期续期，处理中的键从当前时刻起续、已
  完成的键从完成时刻起续；`ttl` 省略时用构造时的默认值
- `ttl`：记录存活秒数，`None` 表示永不过期
- `clock`：时间读取统一走它，便于测试注入
- `path`：记录落盘的文件路径，`None` 表示只放内存
- `max_result_size`：结果体积上限（JSON 编码后的字节数），`None` 表示
  不限；超限结果只保存一份 `TruncatedResult` 截断标记（含 `truncated`、
  `original_size`、`size_limit`），`get` 回标记而不是原始回执，调用方应
  据此走对账/补查；从 `idemkey` 可直接导入 `TruncatedResult`

记录字段：`result` 保存结果，`created_at` 是键被占上的时刻，`finished_at`
是收尾时刻，`expires_at` 是到期时刻。有效期对已完成记录从 `finished_at`
起算，对处理中的占位从 `created_at` 起算。内部一把锁保护，磁盘读写也在
锁内完成，落盘走临时文件 + `os.replace` 原子替换。

典型用法（失败回滚 + 超长结果识别）：

```python
store = IdempotencyStore(ttl=3600, clock=time.time, path="idem.json",
                         max_result_size=65536)
if not store.begin(order_id):
    return store.get(order_id)
try:
    result = charge(order_id)
except Exception:
    store.rollback(order_id)
    raise
stored = store.finish(order_id, result)
if isinstance(stored, TruncatedResult):
    schedule_reconcile(order_id)
return result
```

落盘 + 重启场景请使用跨重启稳定的时钟（例如 `time.time`）；默认的
`time.monotonic` 每次进程启动会重新起算，只适合纯内存使用。

## 运行

```bash
python3 demo.py                          # 现象演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## Known Issues

以下问题已在当前版本修复，按线上对账发现的顺序记录根因与修法。

### 1. 只差大小写的单号被并成一笔（重复扣款）

- 现象：`Order-7001` 与 `order-7001` 两笔单，后一笔 `begin` 直接拿到
  `False`，`get` 回的是前一笔的回执；运营以为没扣成功又补发，用户被
  多扣一次。
- 根因：`_normalize` 对键做了 `strip().lower()`，把大小写差异折掉。
  幂等键应当按字面值匹配，大小写不同就是两个不同的键。
- 修法：规范化只保留 `strip()`，不再转小写；落盘文件也按原始键名保存。
  回归测试：`TestCaseSensitiveKeys`。

### 2. 重启后键还在、结果没了（重发全被判重复卡住）

- 现象：服务半夜重启，处理过的单子一个结果都取不回，但键都还在，重发
  一律 `begin=False`，业务卡死。
- 根因：`begin` 占键时会 `_save()`，而 `finish` 只改内存、从不落盘，
  磁盘上永远只有 `result=None` 的空占位；重启加载后自然全是空结果。
- 修法：`finish`（以及 `rollback`、`renew`）在锁内落盘；写入改为临时
  文件 `fsync` 后 `os.replace` 原子替换，避免写到一半崩溃留下坏文件。
  回归测试：`TestPersistenceOnFinish`。

### 3. 处理中途失败，键从此卡死（重发只回空结果）

- 现象：下游超时，单子没走到 `finish`；之后无论重发多少次都是
  `begin=False` + `get=None`。
- 根因：`begin` 先写一个“未完成占位”防并发，但没有任何失败出口能撤
  回它；落盘文件里带过去的未完成占位在重启后同样永久占位。
- 修法：新增 `rollback(key)`，只删除尚未 `finish` 的占位（已完成记录
  绝不回滚，防止抹掉真实回执）；加载落盘文件时直接丢弃未完成的占位
  （那属于已死进程，本进程不再持有那次处理）；未完成占位本身仍按
  `ttl` 到期，双保险。调用方在 `begin` 后用 try/except 包住处理逻辑，
  失败时 `rollback`。回归测试：`TestRollback`。

### 4. 耗时单刚收工就“不认识”（有效期被提前用光）

- 现象：单子处理时间超过 `ttl`，`finish` 之后立刻 `get` 返回 `None`，
  离“完成后保留 ttl 秒”的约定还早。
- 根因：`_purge` 用 `now - created_at >= ttl` 判断过期，TTL 从开工占键
  时刻而不是完成时刻起算。
- 修法：记录改存绝对到期时刻 `expires_at`：`finish` 时以 `finished_at`
  为起点重算窗口，处理中的占位仍从 `created_at` 起算。回归测试：
  `TestTtlFromFinish`。

### 5. 长流程需要中途延长有效期（新增能力）

- 需求：处理时间可能很长的单子，希望不重跑整单也能把有效期往后延。
- 实现：`renew(key, ttl=None)` 原地续期——处理中的键从当前时刻起续，
  已完成的键从完成时刻起续（固定锚点，重复续期不会漂移），省略 `ttl`
  时用构造默认值；返回键是否存在。续期结果同样落盘。测试：
  `TestRenew`。

### 6. 超大结果撑爆缓存（新增能力）

- 需求：回执体积失控时不能把缓存/磁盘顶爆，但取回时要能看出结果没存全。
- 实现：构造参数 `max_result_size`（JSON 编码字节数，默认不限）；超限
  时 `finish` 不保存原文，只存 `TruncatedResult(original_size,
  size_limit)` 标记（`truncated=True`），`get` 与 `finish` 返回值都是该
  标记，键仍算已处理、重复提交照旧回放而不是重新扣款；标记可跨重启
  还原。调用方用 `isinstance(result, TruncatedResult)` 识别并走对账补查。
  测试：`TestTruncation`。
