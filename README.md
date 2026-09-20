# idemretry

交易链路的幂等提交小库：外部调用的结果按幂等键缓存，瞬时故障自动重试，
纯标准库，无外部依赖。时钟可注入，便于演示与测试。

## 模块说明

`idemretry/client.py` 提供 `IdempotentClient`：

- `IdempotentClient(transport, clock=None, ttl=60.0, max_attempts=3)`：
  `transport(key, payload)` 执行真正的副作用并返回结果
- `submit(key, payload)`：提交一笔业务，返回 `Receipt`
- `client.calls`：transport 实际收到的每一次调用

对外契约：

- 首次提交执行一次 `transport`，返回的 `Receipt.replayed` 为假
- 幂等窗口（`ttl` 秒）内同键重复提交，回放同一条回执，不重复执行
- 幂等窗口内已受理、且结果仍在的键，重复提交一律走回放
- 瞬时故障自动重试，最多 `max_attempts` 次尝试（含首次）
- 确定性故障立即上抛，不重试

`idemretry/__init__.py` 导出 `IdempotentClient`、`Receipt`、`TransientError`、
`PermanentError`、`DuplicateKey`、`RetryExhausted`。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues

以下四类对账异常同源于 `idemretry/client.py`，均已修复并配有回归测试
（`tests/test_regression.py`）：

- **重试导致重复扣款**：`_send` 曾给每次尝试拼接 `key#attempt` 新键再发给
  下游，下游按提交键去重因此失效，重试被当成新单重复执行副作用。修复后
  重试一律携带原始幂等键，`client.calls` 记录与 transport 实际收到的
  调用保持一致。
- **重试耗尽后同键重发被判 DuplicateKey**：`submit` 在执行前就把键写入
  占位表，失败后从不清理，键要占满整个 `ttl`，期间同键重发一律被误判
  为重复提交。修复后只要提交未成功（`RetryExhausted`、`PermanentError`
  等），占位键立即释放，同键重发会被重新受理。
- **成功后半分钟内同键重发拿不到回执**：结果缓存曾使用硬编码的 30 秒
  保留期，短于幂等窗口 `ttl`；结果先过期而键未过期，同键提交走不到回放
  分支，反而抛 `DuplicateKey`。修复后结果缓存与幂等键同生命周期，窗口
  内同键提交总能回放到原回执。
- **配置三次尝试实际只打两次**：`_attempt_loop` 的循环上界误写为
  `max_attempts - 1`，差一错误导致尝试预算少打一次。修复后严格按
  `max_attempts` 次（含首次）执行。
