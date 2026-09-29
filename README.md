# mutexly

进程间互斥器工具，纯标准库，无外部依赖。

## 现状

mutexly/lock.py 提供朴素本地锁 LocalLock：

- LocalLock()：内部就一把 threading.Lock，不接任何外部协调
- acquire(owner)：非阻塞拿本地锁，拿到记下 owner 返回 True，已被别人持有返回 False
- release(owner)：只有当前持有者本人能释放，成功返回 True
- holder() / is_locked()：只读探查
- 只在同一个解释器内有效，多进程或分布式下完全不协调

## 目标

见任务描述。约束：

- 现有行为与 tests/test_lock.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
