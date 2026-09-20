# loglite

仓库巡检工具包：扫描 -> 核查 -> 处置 三段流水线，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `loglite/manifest.py` 清单文本与条目元组互转（`name size mtime`，# 注释）
- `loglite/scanner.py` 可疑条目筛选（临时后缀 / 超大小上限），前缀 `[scanner]`
- `loglite/checker.py` 重复条目与异常 mtime 核查，前缀 `==> checker:`
- `loglite/planner.py` 问题编排成处置动作，前缀 `[planner]`

三个功能模块的过程日志目前都是裸 `print`，格式各自为政。

## 约束

- `tests/test_pipeline.py` 锁定了返回值与 stdout 输出（含逐行文本），一个字不改
- 纯标准库，Python 3.8+

## 接入结构化日志

```python
from loglite.logging import configure, get_logger, set_context, clear_context, FileSink

configure(level="INFO", sinks=[FileSink("run.log", max_bytes=10<<20, backups=5)])
log = get_logger("scanner")
log.debug("...")  # DEBUG/INFO/WARNING/ERROR，低于全局级别不进 sink
token = set_context(job="nightly", host="n1")  # threading.local，线程隔离
log.info("自动带上下文")
clear_context(token)  # 弹一层回到上层；也可 with set_context(...)
```

- 默认 `StreamSink` + PLAIN 渲染只输出消息正文，与旧 print 的 stdout 逐行一致；`FileSink` 输出 JSONL，超 `max_bytes` 轮成 `run.log.1/.2...`，只留 `backups` 个
- 写与轮转共用一把锁，多线程并发写爆时轮转只发生一次，期间等待的日志不丢
- 另有 `CaptureSink`（内存捕获）与 `StreamSink(stream, render="json")` 供测试/自定义采集

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
