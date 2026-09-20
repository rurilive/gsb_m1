# spillkit

超内存数据的排序去重工具，纯标准库，无外部依赖。记录是单行文本，
默认以第一个制表符之前的内容作为排序键；同一个键只保留最先进入的
那一条。缓冲区攒满 memory_limit 条就排序落成一个 run 文件，最后
把全部 run 文件归并成一个有序结果。

## 现状

`spillkit/sorter.py` 提供 `SortDeduper`：

- `SortDeduper(workdir=None, memory_limit=4096, fd_limit=8, key=None)`：
  workdir 默认新建临时目录；memory_limit 是内存里最多攒的记录条数；
  fd_limit 是同时打开的 run 文件数上限，归并的中间输出和最终输出
  同样占额度；key 默认取第一个制表符之前的内容
- `add(record)`：收一条记录，缓冲满即落盘
- `finish()`：返回排序去重后的记录列表
- `close()`：删掉本次排序产生的全部 run 文件和临时目录
- `stats()`：`records_in` / `runs_written` / `merge_passes` /
  `peak_buffered` / `peak_open_runs`

`sort_dedup(records, ...)` 是喂完一批记录直接拿结果的便利函数。

`spillkit/runfile.py` 负责 run 文件的编码读写：每行一条记录，格式
是序号加制表符再加原始记录（记录必须是单行文本）。seq 是记录进入
排序器时的全局序号，键相同时靠它判定输入先后。`RunFileGuard` 是
所有 run 文件句柄的唯一入口，同时打开数超过 fd_limit 会抛
`TooManyOpenRuns`（等价于系统的句柄耗尽）。

`spillkit/merge.py` 的 `merge_runs(paths, key, out_path, guard)` 把
若干有序 run 文件归并成一个有序 run 文件。

## 问题

线上反馈：数据量小、完全不落盘时结果一直是对的；数据量一大开始
溢写，输出里就冒出重复行，有时候尾部的一整段数据凭空消失，溢写
文件一多进程还会直接报句柄超限挂掉。细节见任务描述。

## 约束

- 纯标准库，不引三方依赖
- 内存上限是硬约束，任何情况下不能靠全量缓存绕过
- `tests/test_spillkit.py` 是行为基线，一个字不改，必须原样全绿

## 运行

```bash
python3 demo.py                          # 现有现象的复现
python3 demo.py perf                     # 一百万条压测
python3 -m unittest discover -s tests -v # 行为基线测试
```
