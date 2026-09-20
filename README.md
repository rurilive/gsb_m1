# healthd

进程内健康自检包，单进程内嵌，纯标准库，无外部依赖。

## 现状

- `healthd/board.py`：`StatusBoard` 按探针名记录最近一次结果（`record` / `result` / `snapshot` / `overall_ok`），`overall_ok` 要求全部已记录探针都通过，无记录时为 False。
- `healthd/checker.py`：`CheckRunner.register(name, fn)` 注册探针（检查函数无参调用，通过返回细节字符串、失败抛异常），`run_once()` 按注册顺序串行跑一轮并写状态板，单个探针失败不影响后续探针。

行为以 `tests/test_board.py` 与 `tests/test_checker.py` 为准。

## 问题

探针要靠外部手动触发，没有常驻检查；探针本身卡死会把整轮检查拖死，线上出过队列探针 hang 住导致健康检查整体超时的事故。运维现在要求进程自己定期体检，并且把「健不健康」和「能不能接流量」分开说。

## 目标

见任务描述。约束：

- 现有行为保持不变（两个基线测试一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 手动检查演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 就绪语义

- 整体状态三档：全部探针通过为 `ok`；通过数达到门限 `k` 但没全过为 `degraded`；低于 `k`（或首轮之前）为 `down`。
- `status()` 回答「健不健康」，`ready()` 回答「能不能接流量」：通过探针数 `>= k` 即可接流量，所以 `degraded` 通常仍接流，`down` 摘流。
- `register(name, fn, timeout=秒)`：探针超时未返回直接判失败，不再拖死整轮。
- `start()`/`stop()` 起停后台自检线程，每轮间隔在 `[period-jitter, period+jitter]` 间抖动，时钟可注入。
- `on_change(fn)` 在整体状态翻转时由检查线程回调 `fn(old, new)`，回调抛错只记录、不中断检查。
- `snapshot()`、`status()`、`ready()` 均线程安全，读端点可与检查线程并发调用。
