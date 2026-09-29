# poolnex

进程内连接池，纯标准库，无外部依赖。

## 现状

poolnex/pool.py 提供固定上限的连接池 ConnectionPool：

- ConnectionPool(max_size, factory=None, clock=time.monotonic)：max_size 为连接上限，factory 可选自定义建造，clock 为注入时钟
- acquire()：借出连接，池里有空闲就复用，没有空闲且未达上限就新建，达到上限就阻塞等待归还
- release(conn)：归还借出的连接，唤醒等待者；归还不是本池借出的连接抛 ValueError
- stats()：返回 active / idle / created 计数快照
- Connection：带 cid、created_at、is_healthy()、mark_unhealthy()、close()
- 内部一把锁加条件变量保护，多线程借还安全

## 问题

借出没有时限，池满时调用方被无限期挂住；连接用久了可能失效，池照旧借出坏连接；
空闲连接积压不回收；池也没有关闭语义，下线时在借连接无从处置。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_pool.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```