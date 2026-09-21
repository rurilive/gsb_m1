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
- `release(key)`：放开一个还没收尾的占位（处理中途失败时调用），之后同一
  个键可以重新 `begin`；已收尾的键不受影响
- `renew(key)`：给键续期，把存活计时点推到当前时刻；长流程可以中途延长
  占位寿命而不必整单重跑，已收尾的键则从当前时刻重新计一个 ttl
- `ttl`：记录存活秒数，`None` 表示永不过期
- `clock`：时间读取统一走它，便于测试注入
- `path`：记录落盘的文件路径，`None` 表示只放内存
- `max_result_size`：单个结果的体积上限（JSON 序列化后的 UTF-8 字节数），
  `None` 表示不限。超限结果不进缓存，替换为 `TruncatedResult` 截断标记

记录字段：`result` 保存结果，`created_at` 是键被占上的时刻，`finished_at`
是收尾时刻。内部一把锁保护，磁盘读写也在锁内完成，落盘走临时文件 +
`os.replace` 原子替换，避免写到一半把老记录毁了。

键只做首尾空白裁剪，**不做大小写折叠**——大小写是单号的一部分。

### 截断标记

结果体积超过 `max_result_size` 时，`finish` 存下并返回一个
`TruncatedResult(original_size, max_size)`，它的 `truncated` 属性恒为
`True`。`get` 取回时调用方据此区分"正常回执"和"这条被截断过、需要另行
对账"，标记本身也会一起落盘、重启后还原：

```python
from idemkey import IdempotencyStore, TruncatedResult

store = IdempotencyStore(max_result_size=4096)
result = store.finish("pay-1", huge_payload)
if isinstance(result, TruncatedResult):  # 或 result.truncated
    ...  # 结果没进缓存，走兜底/对账
```

## 运行

```bash
python3 demo.py                          # 现象演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## Known Issues

以下四类线上事故的根因均已修复（对应 `tests/test_regressions.py` 中的
回归用例）：

1. **只差大小写的两笔单被当成同一笔，后一笔回放前一笔的回执，运营误判
   补发导致重复扣款。**
   - 根因：键规范化时做了 `key.strip().lower()`，`Order-7001` 与
     `order-7001` 被折叠成同一个键，后一笔 `begin` 直接返回已存在。
   - 修法：`_normalize` 只裁剪首尾空白，不再折叠大小写；大小写不同的键
     各自独立记录、各自回放。
2. **服务半夜重启后，处理过的单子结果全取不回，但键还在，重发全部被判
   重复卡死。**
   - 根因：`begin` 占键时会 `_save()` 落盘，`finish` 写结果时却没有
     `_save()`。磁盘上只存得住"占位"，重启后占位复活、结果永远是
     `None`，`begin` 又因占位存在而返回 `False`，单子进退两难。
   - 修法：`finish`（以及 `release`、`renew`）在锁内落盘；落盘改为临时
     文件 + `os.replace` 原子替换，避免写盘中途崩溃留下半截文件。
3. **单子处理到一半下游超时失败，那个键从此起不来工，重发只回空结果。**
   - 根因：`begin` 先写入 `result=None, finished_at=None` 的占位，处理
     失败时代码没有任何途径清掉它；之后 `begin` 永远返回 `False`，
     `get` 永远回放 `None`。
   - 修法：新增 `release(key)`，处理失败（捕获到异常）时放开未收尾的
     占位，同一键即可重新 `begin`；已收尾的结果不受影响。作为兜底，
     没人 `release` 的崩溃残留占位也会按 `created_at + ttl` 过期，不会
     永久占键。
4. **耗时单子刚收工去取就说不认识，离有效期还早。**
   - 根因：过期判定锚在 `created_at`（占键/开工时刻），处理耗时一旦超过
     `ttl`，`finish` 之后的第一次 `get` 里 `_purge` 就把记录清掉了。
   - 修法：过期锚点改为"完成时刻 `finished_at` 优先，未收尾占位才退回
     `created_at`"，结果从收工时刻起完整存活一个 `ttl`。配套新增
    `renew(key)`，长流程可中途把占位计时点推到当前时刻，不必整单重跑。

另增强一项：

5. **超大结果可能撑爆内存/磁盘缓存。**
   - 修法：构造参数新增 `max_result_size`，超限结果不进缓存，替换成
     `TruncatedResult` 截断标记（带 `truncated`、`original_size`、
     `max_size`），取回方一眼能看出被截断过；标记同样可落盘还原。

使用上仍需注意：默认 `clock=time.monotonic` 只在单进程内有意义，跨
重启做 `path` 持久化时应注入同一时间基准的时钟（如 `time.time`）。
