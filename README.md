# loglite

仓库巡检工具包：扫描 -> 核查 -> 处置 三段流水线，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `loglite/manifest.py` 清单文本与条目元组互转（`name size mtime`，# 注释）
- `loglite/scanner.py` 可疑条目筛选（临时后缀 / 超大小上限），前缀 `[scanner]`
- `loglite/checker.py` 重复条目与异常 mtime 核查，前缀 `==> checker:`
- `loglite/planner.py` 问题编排成处置动作，前缀 `[planner]`

三个功能模块的过程日志统一走 `loglite/logging.py` 结构化日志层，
默认兼容渲染（裸消息、无装饰），输出与历史裸 `print` 逐行一致。

## 接入

- `from .logging import get_logger; log = get_logger("subsystem")`
- 级别 `DEBUG/INFO/WARNING/ERROR`：`configure(level="INFO")`，低于全局级别不进 sink
- `with set_context(batch="n", stage="scan"):` 自动随记录带字段，弹一层回上一层，线程隔离
- sink：`StreamSink`（stdout/兼容渲染）、`RotatingFileSink(path, max_bytes, backups)` 按大小轮成 `path.1/.2`，并发不丢不重
- 结构化渲染 `render_plain` / `render_json`，测试断言用 `CaptureSink`

## 约束

- `tests/test_pipeline.py` 锁定了返回值与 stdout 输出（含逐行文本），一个字不改
- 纯标准库，Python 3.8+

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
