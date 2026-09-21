# cdcparse

本地 binlog 风格事件流的读取与投递，纯标准库，无外部依赖。

## 日志格式

一行一个事件，位点写在行内：

```
{"pos": 1, "type": "begin", "xid": 21}
{"pos": 2, "type": "data", "xid": 21, "op": "insert", "table": "orders", "row": {"id": 1}}
{"pos": 3, "type": "commit", "xid": 21}
{"pos": 4, "type": "ddl", "sql": "alter table orders add column note varchar(32)"}
```

`type` 有 begin / commit / data / ddl 四种；data 的 `op` 有 insert / update / delete。
同一条 data 事件的 `xid` 与包住它的 begin、commit 一致。

## 现状

- `cdcparse/events.py`：`Event` 模型、`parse_line()` 解析、`begin_line()` 等构造行、
  `txn_lines(start_pos, xid, changes)` 把一组行变更包成连号的事务行
- `cdcparse/stream.py`：`MemorySource(lines)` 与 `FileSource(path)` 按到达顺序吐行（不排序、不去重），
  `EventReader(source)` 的 `read_event()` 一次读一条，流末返回 None，坏行抛 `ParseError`，
  `at_end()` 探测是否还有下一行，`arrivals` 与 `position` 记录读过的行数与最后位点
- `cdcparse/sink.py`：`MemorySink` 的 `apply(changes)` 接一批变更，`changes()` / `pos_list()` / `stats()` 查收成
- `cdcparse/relay.py`：`StreamRelay(reader, sink).pump()` 读到一条 data 或 ddl 就立刻投给下游

上游写日志的进程可能被 kill，文件尾巴上会留一条写了一半的行；
事件到达顺序也不保证与位点一致，同一条重发过几次是常事。
现有通道对位点、事务边界与 ddl 一律照单转手。

## 目标

见任务描述。约束：

- 现有接口与 `tests/` 基线行为保持不变（基线文件一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 逐条读取与逐条投递演示
python3 -m unittest discover -s tests -v # 既有行为基线测试
```
