# resumex

把上游记录按批喂给下游的搬运器，纯标准库，无外部依赖。

## 现状

`resumex/stream.py` 提供来源、下游与搬运器三件套：

- `MemorySource(records=())`：内存来源，`records` 是可迭代的 `(seq, payload)`，序号须严格递增
  - `append(seq, payload)` 追加一条，序号必须大于已有最大序号
  - `fetch(after_seq, limit)` 取序号大于 `after_seq` 的至多 `limit` 条，按序号递增返回 `Record` 列表
  - `latest_seq` 是最大序号（空为 0），`len(source)` 是条数
- `MemorySink()`：内存下游，`push(records)` 接收一批并返回接收后的水位；`watermark` 是已收到的最大序号，`received()` 按到达顺序返回快照，`stats()` 汇总批数、条数与水位
- `StreamRunner(source, sink, batch_size=2, clock=time.monotonic)`：`run()` 逐批取数推送直到来源没有新记录，返回本次推送条数；`progress()` 返回 `last_seq` / `pushed` / `batches` / `last_at` 快照，`clock` 为注入时钟

进度只活在内存里，进程一停就没了；下游按到达顺序照单全收，不认水位。

## 问题

搬运器重启后从头发，下游重复收下已经处理过的记录。

## 目标

见任务描述。约束：

- 现有方法与 `tests/test_stream.py` 基线行为保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 按批推送演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

1. 双源水位存同一个追加日志（`resumex/resume.py` 的 `WatermarkStore`），每行一条 `rx1|路名|确认序号|时间戳|HMAC`，按路名回放，各路从自己的序号之后取数。
2. 只有下游接收成功后才追加该路水位，重启读同一份文件续推，故已确认的不重喂。
3. 全局水位 = 两路确认序号的最大值；乱序窗口下界 = 全局水位 − `window`，下界之内的迟到记录补入并计 `late_accepted`，之外丢弃计 `dropped`，窗口内重复只计 `duplicates`。
4. 损坏回退点 = 日志中第一个坏行之前最后一个完好行：缺换行的半截行、校验和不符的整行都不是有效值，加载在该处截断坏尾巴并接着写，不整份作废。
5. 每路一个 `BackpressureSink`，某路阻塞时只跳过该路的取数与推送并累加 `blocked`，另一路不受牵连。
