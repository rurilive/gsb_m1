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

- 每个进程持一份向量时钟 `{进程名: 已知条数}`；`record` 时自己的分量加一，时钟副本盖在事件 `vclock` 上
- `observe(proc, src, seq)` 把 src 第 seq 条事件的时钟按分量取 max 并进 proc 的时钟，此后 proc 记的事件自然排在它后面
- `compare(a, b)` 比两条事件的向量时钟：全 <= 且有小于为 `before`，反之为 `after`，全等 `equal`，互有大小 `concurrent`
- `snapshot(observer)` 以 observer 当前向量时钟为 cut，`cut[p]=n` 表示拼进 p 的前 n 条本地事件，`events` 按进程分组
- 向量时钟对因果历史闭合，切点不会停在半截事件上，快照天然一致
- `Snapshot.compare` 比两份 cut：包含关系定 `newer`/`older`，全等 `equal`，互不包含 `concurrent`，不硬排
