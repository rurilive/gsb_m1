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
