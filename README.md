# causalsnap

多进程共享状态的进程内骨架，纯标准库，无外部依赖。进程名与时钟都由调用方注入，真实的多机进程在本骨架里用名字顶替。

## 现状

`causalsnap/store.py` 提供 `CausalStore`：

- `CausalStore(clock=time.monotonic)`：clock 为注入时钟，落笔时刻取自它
- `record(proc, payload)` 在 proc 本地记一个事件，返回它的序号（每个进程各自从 0 起）
- `local(proc)` 返回该进程的事件序列（元组副本），`last(proc)` 返回最近一条或 None
- `processes()` 返回出现过的进程名，字典序
- `Event` 带 `proc` / `seq` / `payload` / `at` 四个字段，同一 `(proc, seq)` 视为同一条事件
- 共享单元用 `publish(proc, key, value)` / `fetch(key, default=None)` 读写，`cells()` 列出全部 key
- 内部一把锁保护，单操作多线程安全

事件只按本地序号排列，存储不关心任何跨进程的先后。

## 问题

两个进程各自记下的事件，本地序号谁大谁小说明不了任何因果关系；也没有任何办法取出一份各进程都停在事件边界上的全局视图，更难判断两份视图谁更新。

## 目标

见任务描述。约束：

- 现有方法与 `tests/test_store.py` 基线行为保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 本地事件与共享单元演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 每个进程持有一份向量时钟（proc -> 已知的最大序号）；`record` 时自己的分量涨到新事件序号，事件带走当时知识的副本。
- `observe(proc, src, seq)` 把 src 第 seq 条事件的向量时钟按分量取 max 并进 proc 的知识，从它的下一条本地事件起生效。
- `compare(a, b)` 逐分量比两条事件的向量时钟：全不劣且至少一处更小为 before，反之为 after，互有胜负为 concurrent，相同为 equal。
- `snapshot(observer)` 用观察者当前知识当切点：`cut[p]` 表示 p 的本地事件算到第几条，`events` 按进程分组收录 0..cut[p]。
- 知识只经 record/observe 单调增长且整段合并，切点天然闭合，不含因果前置缺失的"半截"事件。
- `Snapshot.compare` 逐进程比 cut：全不劣且至少一处更靠后为 newer，反之为 older，互有胜负为 concurrent，相同为 equal，不做硬排。
