# replog

一个纯标准库的单机追加日志，无外部依赖。复制日志这类系统里都要把一条条变更
按次序记下来再复制到多个副本，replog 就是这一层。

## 现状

- `replog/log.py`：`LocalLog` 维护一条追加日志，序号从 1 开始。
  - `append(term, command)`：在末尾追加一条 `Entry`，返回自增序号
  - `get(index)`：按序号读回某条条目
  - `entries()`：按序号次序返回全部条目的浅拷贝
  - `size()` / `last_index()` / `last_term()`：长度与末尾条目的序号与任期
  - `term_at(index)`：读某序号处条目的任期
  - `truncate_from(index)`：丢掉 index 及其之后的条目，返回被丢掉的条目
  - `commit_index()`：当前已提交到的序号
  - `reset()`：清空全部条目
- `replog/__init__.py` 只导出基线类与错误类型。

现在只有一条单机日志：没有副本，也没有主从，日志不会从一处复制到另一处；
条目记下来了也不知道有没有得到多数认可，更谈不上在多数确认之后才提交；
任期只是一个数字，没有选举；副本落后或有冲突时没有回退与覆盖的路子；
副本崩溃重启后也谈不上依据持久化日志恢复。异常体系以 `RepLogError` 为基类，
`InvalidIndex` / `UnknownNode` 是两种现有具体错误。

## 目标（见任务描述）

见任务描述。约束：

- 现有行为与 `tests/test_log.py` 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+
- 网络用可注入的确定消息队列，同一输入必须跑出同一结果
- 非法序号 fail fast，空日志语义明确
- 所有错误继承 `RepLogError`

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
