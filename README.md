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

测试文件：`tests/test_pool.py`（纯标准库 `unittest`）。运行：

```bash
python3 -m unittest tests.test_pool -v
# 或
python3 tests/test_pool.py
```

共 15 个用例：12 绿、3 红。多轮重复运行及随机 `PYTHONHASHSEED` 下结果稳定
（恒为 3 红）。并发用例全部用 `threading.Barrier`/`Event` 对齐节奏、
`join(timeout)` 收尾，无裸 `sleep` 赌时序；等待窗口给 10s 余量（实际为
毫秒级）。

### 红用例（3 个，均为源码与 README 不符的缺陷）

1. `TestUnhealthyReturn.test_unhealthy_connection_closed_and_never_requeued`
   - 对应 README 2：坏连接归还必须立即 `close()` 丢弃。
   - 缺陷：`return_conn()` 从不检查 `conn.healthy`，坏连接被原样放回
     空闲队列，下一个 `borrow()` 会把它再次借出（线上拿到坏连接的怪事
     即源于此）。
   - 修复方向（一句话）：`return_conn()` 先判 `healthy`，为 False 时只从
     `_inflight` 摘除并 `close()`，不入 `_idle`，同时 `notify_all()`
     让等待者走「未满则新建」分支。
2. `TestReadmeDiscrepancies.test_waiting_borrower_woken_on_every_return`
   - 对应 README 1：等待期间有连接归还，等待者应立即拿到、抢不到的继续等。
   - 缺陷：`borrow()` 在池满分支只 `wait()` 一次，醒来没抢到空闲连接就
     直接抛 `BorrowTimeout`，不重算 deadline 也不重查；配合
     `return_conn()` 的 `notify_all()`，池满时一次归还会把全部等待者
     吵醒，抢到的拿连接，其余全部误报超时（虚假超时）。
   - 修复方向（一句话）：池满分支改成 `while not _idle and not _closed:`
     循环等待，用 `wait(deadline - now)` 重算剩余时间，直到拿到连接、
     池关闭或真正到 deadline 才返回。
3. `TestReadmeDiscrepancies.test_close_immediately_wakes_waiting_borrowers`
   - 对应 README 3：`close()` 必须立即唤醒等待中的 `borrow()`。
   - 缺陷：`close()` 只置 `_closed`、关空闲连接，没有 `notify_all()`，
     等待者会一直睡到自己的 timeout 才收到 `PoolClosedError`（关闭池时
     调用方被挂住的现象即源于此）。
   - 修复方向（一句话）：`close()` 在置位并清空空闲后调用
     `_cond.notify_all()`；依赖缺陷 2 的循环修复，等待者醒来重查
     `_closed` 后立即抛 `PoolClosedError`。

### 并发用例设计

- `test_created_never_exceeds_max_size_under_burst`（绿）：8 线程在
  `Barrier(8)` 后同时冲击 `max_size=2` 的池；先轮询确认稳定在
  「2 在途 + 6 个真实阻塞在 Condition 上的等待者」，断言
  `stats()["created"] == 2`；再用 `Event` 统一放行归还，结束后断言
  在途清零且 `created` 仍为 2（锁 README 4）。
- `test_concurrent_borrow_return_churn`（绿）：8 线程经同一个
  `Event` 同时开跑，各做 100 轮借还，过程中大量线程真实经历池满等待；
  断言无任何异常、结束后在途清零、`created <= max_size`（README 4）。
- 上述「立即拿到归还连接」与「close 立即唤醒」两个红用例同样是真实
  多线程：测试线程先阻塞在 `borrow()`（通过 Condition 等待队列长度
  确认已真正睡下），主线程再归还/关池，断言等待线程在远小于 timeout 的
  窗口内结束并得到预期结果，从而把时序钉死。

### 说明：README 未约定、未钉成红用例的行为

- `borrow()` 不传 `timeout` 时默认取构造参数 `borrow_timeout`
  （README 只写了 `timeout=None` 的接口签名，未定义默认值）。
- README 2「坏连接丢弃」与 README 4「`created <= max_size`」在
  max_size 全在途、其中有坏连接归还的场景下存在张力（丢弃坏连接后新建
  可能使 `created` 累计超过 `max_size`）：这是 README 内部的口径问题
  （「创建总数累计」还是「同时存活连接数」），不是源码单方面的偏差，
  因此未钉红用例，建议明确第 4 条的统计口径。
