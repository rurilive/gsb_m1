# netpool

服务进程内的连接池，多线程环境使用，纯标准库（threading + Condition）。连接对象用
`FakeConn` 模拟（接口与真实 socket 对齐：`close()` / `healthy` 属性 / `cid`）。

## 语义约定（以下为本模块的正式行为定义）

1. **borrow(timeout=None)**
   - 有空闲连接 → 直接取出并标记为在途
   - 无空闲但池未满（在途数 < max_size）→ 用 factory 新建一个
   - 池满 → 等待归还；**等待期间只要有连接归还，应立即拿到它**；到 deadline 仍没有 → 抛 `BorrowTimeout`
   - 池已关闭 → 抛 `PoolClosedError`
2. **return_conn(conn)**
   - 归还连接进空闲队列，并唤醒等待者
   - **`conn.healthy` 为 False 的连接：归还时应立即 `close()` 并丢弃，绝不回到空闲队列**（下游健康探测已判死）
   - 归还非本池借出的连接 → `ValueError`
3. **close()**
   - 幂等；关闭所有空闲连接
   - **正在 `borrow` 中等待的调用方必须立即收到 `PoolClosedError`**，不允许等到超时
   - 在途连接随后归还时：直接 `close()` 丢弃，不进池
4. 连接创建总数不超过 `max_size`（`stats()["created"] <= max_size`）

## 运行

```bash
python3 demo.py
```

## 测试报告

测试文件：`tests/test_pool.py`（标准库 unittest，仓库根目录下
`python3 -m unittest discover -s tests -v` 或 `python3 tests/test_pool.py`）。
共 12 条用例：9 绿 3 红，重复运行结果稳定。3 条红用例各对应一处源码与
README 语义约定的出入：

1. `test_close_wakes_waiting_borrower_immediately`（红，对应第 3 条）
   - 缺陷：`close()` 只置 `_closed` 标志、从不 `notify` 条件变量，正在
     `borrow` 中等待的线程不会被立即唤醒，而是睡到 timeout 后拿到
     `BorrowTimeout`，而非 README 要求的"立即收到 `PoolClosedError`"。
   - 修复方向：`close()` 在 `_closed = True` 之后调用 `self._cond.notify_all()`。
2. `test_waiter_keeps_waiting_when_it_misses_a_wakeup`（红，对应第 1 条）
   - 缺陷：`borrow` 池满后只 `wait()` 一次、没有循环重查；多个等待者被
     同时唤醒而归还的连接只够一个时，没抢到的等待者在 deadline 之前就直接
     抛 `BorrowTimeout`，违反了"到 deadline 仍没有才抛"。
   - 修复方向：把等待改成 `while` 循环，每次被唤醒后重查空闲队列 / 关闭标志 /
     deadline，未到 deadline 就用剩余时间继续 `wait(remaining)`。
3. `test_unhealthy_conn_is_closed_and_discarded_on_return`（红，对应第 2 条）
   - 缺陷：`return_conn` 不检查 `conn.healthy`，`healthy=False` 的死连接
     既不 `close()` 也被原样放回空闲队列，下一次 `borrow` 会把死连接再次发出。
   - 修复方向：`return_conn` 归还时先判 `conn.healthy`，为 False 则
     `conn.close()` 后直接丢弃（不进 `_idle`），并 `notify` 让等待者去新建连接。

其余 9 条绿用例覆盖了：空闲复用与在途标记、池未满新建、`BorrowTimeout` 按
deadline 触发、关闭后 borrow 抛 `PoolClosedError`、非法/重复归还抛
`ValueError`、归还唤醒等待者（真实并发）、`close` 幂等且关闭空闲连接、关闭后
在途连接归还即丢弃、8 线程并发压力下 `created <= max_size` 且账目自洽。
