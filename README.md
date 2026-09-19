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

测试位于 `tests/test_pool.py`（标准库 unittest，可独立重复运行）：

```bash
python3 -m unittest discover -s tests -v
```

结果：12 个用例，9 绿 3 红。3 个红用例钉出的正是源码与上文「语义约定」的出入：

1. `test_unhealthy_returned_conn_is_closed_and_discarded`（对应语义 2）
   缺陷：`return_conn` 不检查 `conn.healthy`，已被下游判死的连接原样回到空闲队列，
   下次 `borrow` 会再次发出去。修复方向：归还时检查 `healthy`，为 False 则立即
   `close()` 丢弃、不进空闲队列（并唤醒等待者，让其按语义新建连接）。
2. `test_close_wakes_waiting_borrower_immediately`（对应语义 3）
   缺陷：`close()` 只置 `_closed` 标志、从不 `notify`，等待中的 `borrow` 要睡满
   整个 timeout 被 wait 超时唤醒后才抛 `PoolClosedError`（实测 2.0s 后才返回）。
   修复方向：`close()` 置标志后调用 `cond.notify_all()`，让等待者立即看到关闭状态。
3. `test_full_pool_multiple_waiters_no_premature_timeout`（对应语义 1）
   缺陷：多个等待者被 `notify_all` 同时唤醒后，没抢到连接的等待者不会回到等待，
   而是远早于 deadline 直接抛 `BorrowTimeout`。修复方向：把单次 `wait` 改为
   while 循环，每次按剩余 deadline 重算等待时长，真到点才抛超时。

并发用例设计（threading + Event 定死节奏，不依赖时序碰运气）：

- 等待/唤醒类用例：等待线程先 `Event.set()` 再进 `borrow`，主线程确认事件后
  留 0.2–0.5s 余量确保其已进入 `cond.wait`，再执行 `return_conn`/`close`，
  用 `join(timeout)` 收敛线程并断言线程均已结束。
- 多等待者用例：max_size=1，两个等待者都阻塞后才归还唯一连接，断言两者都能
  在 timeout 内轮流拿到连接（红：没抢到的那个被提前抛 `BorrowTimeout`）。
- `created <= max_size` churn 用例：4 线程 × 50 轮借还，`Event` 统一放行制造
  真实并发，结束后断言无异常且 `created` 不超上限。
