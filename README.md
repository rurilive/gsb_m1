# resumex

把上游记录按批喂给下游的搬运器，纯标准库，无外部依赖。

## 构成

`resumex/stream.py` 提供来源、下游与搬运器三件套（基线，行为不变）：

- `MemorySource(records=())`：内存来源，`records` 是可迭代的 `(seq, payload)`，序号须严格递增
  - `append(seq, payload)` 追加一条，序号必须大于已有最大序号
  - `fetch(after_seq, limit)` 取序号大于 `after_seq` 的至多 `limit` 条，按序号递增返回 `Record` 列表
  - `latest_seq` 是最大序号（空为 0），`len(source)` 是条数
- `MemorySink()`：内存下游，`push(records)` 接收一批并返回接收后的水位；`watermark` 是已收到的最大序号，`received()` 按到达顺序返回快照，`stats()` 汇总批数、条数与水位
- `StreamRunner(source, sink, batch_size=2, clock=time.monotonic)`：`run()` 逐批取数推送直到来源没有新记录，返回本次推送条数；`progress()` 返回 `last_seq` / `pushed` / `batches` / `last_at` 快照，`clock` 为注入时钟

进度只活在内存里，进程一停就没了；下游按到达顺序照单全收，不认水位。

`resumex/resume.py` 提供双源续传三件套：

- `WatermarkStore(path)`：分路水位落盘；`get(lane)` / `positions()` /
  `commit({lane: seq})`，`stats()` 给出提交次数、判废行数、回退次数
- `BackpressureGate(clock=...)`：单路就绪闸门，`close()` / `open()`，
  阻塞轮次单独计数
- `MergeRunner(sources, sink, store, window=5, batch_size=10, gates=None,
  clock=...)`：`run()` 逐路取数合并推送，返回本次喂给下游条数；
  `global_watermark()` 与 `stats()` 给出全局水位、迟到补入/超窗丢弃/
  重复计数及每路取数、阻塞情况

## 实现说明

1. 双源水位存同一个文件，每路一行 `lane|seq|crc32`，推完一批即提交；重启按各 lane 水位之后取数。
2. 提交先把主文件原子改名为 `.bak` 再写新主文件并 fsync，任何时刻至少有一份完好快照。
3. 半截行、坏 crc 行只判废该行并计数，完好行照用，水位停在上一条完好值。
4. 主文件头损坏或缺失则整份退回 `.bak` 的上一个完好点，记一次 fallback，绝不清零重来。
5. 乱序窗口以全局水位 W 界：`G-W <= seq < G` 补入，`seq < G-W` 丢弃并计数，`seq=G` 当重复不喂。
6. 背压按路各持一个闸门：关闭的一路跳过取数、单记阻塞轮次，另一路不受牵连，恢复后窗口内迟到补齐。

## 运行

```bash
python3 demo.py                          # 按批推送演示
python3 -m unittest discover -s tests -v # 基线 + 双源续传测试
```
