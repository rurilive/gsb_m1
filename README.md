# spanweave

把本地采集到的调用链 span 重建成调用树的小库：按 trace 分组挂树，输出缩进
文本、缓存用的规范快照、统计摘要和关键路径分析。只依赖 Python 标准库，数据
从采集队列里来，到达顺序就是队列顺序。

## 快速上手

```python
from spanweave import SpanStore, build, critical_path, render_tree, snapshot, summary

records = [
    {"trace_id": "tr-1", "span_id": "s1", "parent_id": None, "name": "handle",
     "service": "api", "start_ms": 0, "end_ms": 42},
    {"trace_id": "tr-1", "span_id": "s2", "parent_id": "s1", "name": "query",
     "service": "mysql", "start_ms": 10, "end_ms": 20},
]

trees = build(records)
print(render_tree(trees[0]))
print(snapshot(trees[0]))
print(summary(trees[0]))
print(critical_path(trees[0]))
```

流式收数走 `SpanStore`：`feed(records)` 按到达顺序吃记录（可以分多批），
`traces()` 把缓冲里的 span 重建为 `Tree` 列表。

## 数据与契约

记录是 dict，字段 `trace_id`、`span_id`、`parent_id`（可为 None 或缺失）、
`name`、`service`、`start_ms`、`end_ms`，时间是整数毫秒。

- `span_id` 全局标识一条 span；同一条被重传时只保留先到的那条记录。
- `parent_id` 为空（None、缺失或空串）的 span 是它所在 trace 的根，一个
  trace 允许多个根（链路被拆到多个进程上报时就会出现）。
- `parent_id` 指向的 span 还没到达时先记着，等它到达后再挂上去；如果父
  始终没出现，或者指向自身、和别的 span 互相指向成环，这条 span 归入
  `Tree.unresolved`，不丢，也不许把环挂进树里。
- 兄弟之间、根之间都按 `start_ms` 升序排，`start_ms` 相同按 `span_id`
  字典序升序。同一批 span 不管以什么顺序喂进来，重建结果必须逐字节一致。
- 耗时非负：`end_ms` 小于 `start_ms` 说明采集端时钟回拨过，这条 span 的
  耗时按 0 计，条数记在 `summary` 的 `clock_skew` 里。
- `spanweave/render.py` 的 `render_tree` 一行一个 span：两个空格一层缩进，
  行内容为 `名字 (耗时ms)`；`snapshot` 第一行是 `trace %s`（trace_id），
  之后 `缩进span_id 服务名 耗时ms`，服务名缺省时用 `-`。
- `summary` 返回 dict，键为 `spans`、`roots`、`unresolved`、`clock_skew`、
  `total_ms`、`max_depth`，根的深度是 0。
- `critical_path` 返回从根到叶耗时之和最大的那条链的 span_id 列表，并列时
  取 span_id 序列字典序最小的那条。

重建是采集管线的热路径：十万条 span 的 trace 从喂数到挂树、统计加关键路径
要在五秒内跑完；几千层的深链也要能正常渲染和统计。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```
