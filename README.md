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

运行方式（仓库根目录，两种均可，无需额外依赖）：

```bash
python3 -m unittest tests.test_pool -v
python3 tests/test_pool.py
```

共 13 个用例：10 绿、3 红。3 个红用例对应 3 处源码与 README 的实质出入，
其余语义（空闲直取/池未满新建、单等待者归还即得、超时抛 `BorrowTimeout`、
非本池连接或重复归还抛 `ValueError`、`close()` 幂等且关闭空闲连接、关闭后
在途归还直接丢弃、高并发下 `created <= max_size` 等）均符合约定，为绿用例。

### 红用例与缺陷

1. `test_red_unhealthy_conn_closed_and_dropped_on_return`
   - 缺陷：`return_conn` 不检查 `conn.healthy`，已判死的连接照常进空闲队列，
     被下一个 `borrow` 二次发放（违反第 2 条）。
   - 修复方向：归还时若 `healthy` 为 False，立即 `conn.close()` 且不入 `_idle`。
2. `test_red_close_wakes_waiting_borrow_immediately`
   - 缺陷：`close()` 只置 `_closed`、关闭空闲连接，没有 `notify_all()`，等待者
     一直睡到自己的 timeout，且最终抛的是 `BorrowTimeout` 而非
     `PoolClosedError`（违反第 3 条）。
   - 修复方向：`close()` 末尾在持锁状态下 `self._cond.notify_all()`，并让
     `borrow` 的等待循环在被唤醒且看到 `_closed` 时立即抛 `PoolClosedError`。
3. `test_red_one_returned_conn_serves_one_waiter_without_false_timeout`
   - 缺陷：池满、多等待者并发时，`borrow` 只 `wait` 一次、醒来后不重新检查
     条件也不按剩余时间继续等待；`notify_all` 惊群中没抢到连接的等待者直接
     落到函数末尾 `raise BorrowTimeout`，尽管 deadline 远未到（违反第 1 条
     “等待期间只要有连接归还，应立即拿到它；到 deadline 仍没有才超时”）。
   - 修复方向：改为 `while not <可取连接> and not closed and 剩余时间 > 0:`
     循环 `wait(剩余时间)`，醒来重查空闲/关闭状态，虚假唤醒时继续等待。

### 并发用例设计

- 所有多线程用例均为真实线程（`threading.Thread`），不 mock 任何同步原语。
- 节奏由 `threading.Event` / `threading.Barrier` 定死：归还、关闭等动作一律
  先等待竞争线程确实进入 `Condition.wait()`（通过 Condition 内部等待队列
  `_waiters` 长度确认，等待本身带 5 秒断言超时），再触发，避免“先 notify
  后 wait”这类时序巧合。
- “立即唤醒”判定窗口为 1 秒（Condition 真实唤醒为毫秒级），余量充足又能让
  红用例快速失败，不依赖等待者自身的长 timeout。
- 结果判定只基于 Event 是否被 set、线程是否存活、stats 快照；断言 deadline
  统一 5 秒，全量 13 用例约 1.3 秒，可独立重复运行。
- `created` 上限用例：12 线程经 `Barrier` 同时开跑、各 200 轮借还（池
  max_size=4），运行中每轮与结束后均校验 `created <= max_size`。
