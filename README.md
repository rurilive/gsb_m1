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
