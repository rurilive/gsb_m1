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

以下问题均已修复，记录在案便于对账时对照历史版本：

1. **扣款首次超时、自动重试后下游多一条入账（重复扣款）**
   根因：重试时把尝试序号拼进了幂等键（`key#0`、`key#1`……），
   下游按提交键去重，于是同一次提交的重试被当成两笔不同的单子受理。
   修复：所有尝试一律使用原始幂等键，重试由下游按同一提交键去重；
   `client.calls` 中每次调用的键也与 `submit(key, ...)` 完全一致。

2. **重试耗尽失败后，上游立刻用同键重发被判重复提交**
   根因：`submit` 在受理前就把键登记进幂等窗口（保留 `ttl` 秒），
   但 `RetryExhausted`（以及确定性异常）上抛后键并不释放，失败状态被
   缓存成了"已受理"，即使下游早已恢复，同键也只能干等到窗口到期。
   修复：本次受理未产生确定结果（瞬时失败耗尽或确定性失败）时，
   立即释放幂等键，允许调用方立刻用同键重发；真正在途的并发提交
   仍然按 `DuplicateKey` 拦截。

3. **已成功的交易半分钟后同键再发被 `DuplicateKey` 挡回，拿不到回执**
   根因：结果缓存使用独立的 30 秒 TTL（`_RESULT_TTL`），短于幂等
   窗口的 60 秒。30～60 秒之间结果缓存已过期、幂等键却还在，这段
   空窗里重复提交既不能回放回执、又被当成重复拒绝，上游只能另起
   新单，等于再扣一次。修复：结果缓存与幂等键使用同一个 `ttl`，
   窗口内始终走回执回放，到期后才允许重新执行。

4. **配置三次尝试，实际只向下游发出两次**
   根因：尝试循环写作 `range(max_attempts - 1)`，首尝试之后只剩
   `max_attempts - 1` 次实际调用，两次抖动即耗尽。修复：循环改为
   `range(max_attempts)`，"最多 N 次尝试（含首次）"与契约一致，
   `Receipt.attempts` 如实报告实际尝试次数。
