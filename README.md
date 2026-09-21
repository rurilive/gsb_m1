# leasekeeper

调度平台在用的租约发放包，纯标准库，无外部依赖。

## 现状

`leasekeeper/keeper.py` 提供 `LeaseKeeper(clock=time.monotonic)`，按资源发租约：

- `grant(resource, holder, ttl=30.0)`：发一份新租约，记号从 1 起只增；资源上还有活租约抛 `LeaseConflict`
- `renew(lease_id, holder, ttl=None)`：续期，成功返回续后的 Lease；id 不存在、已过期或持有者不对返回 None
- `release(lease_id, holder)`：当前持有者提前归还，成功 True
- `get(resource)` / `resources()`：资源的活租约、还有活租约的资源名（过期的不算）
- `sweep()`：清掉所有已过期租约，返回清掉的 Lease 列表
- `stats()`：发放、冲突、续期、归还、回收、活跃数与最后记号

`leasekeeper/fence.py` 提供 `FenceGuard`：存储层按记号挡旧持有者的闸门，
`check` 放行不小于高水位的记号，落后的抛 `StaleFence`；`seal` 灌历史高
水位，只涨不降。

`leasekeeper/clock.py` 提供 `FakeClock`：手动拨的假时钟，`advance` 往前
拨，`set` 允许往回拨，专门在测试里制造时钟异常的现场。

`leasekeeper/script.py` 提供对拍三件套：`make_script(seed, ...)` 生成确
定性事件脚本（grant、renew、release、sleep 四种事件），`drive(keeper,
script, clock)` 把脚本喂给真实现记下逐条回执，`model_run(script)` 在纸
上算出同样的逐条回执与终局，`as_tuple` 抹平两边类型后逐条比对。

`leasekeeper/bench.py` 量 grant+renew+release 连环吞吐，
`python3 -m leasekeeper.bench` 打印对比表。

## 问题

现在是单机内存版：记号在内存里数，进程一崩全忘；发放没有幂等，重试就
重发；巡检回收是全表扫，几千个节点的规模扛不住。租约台重启后怎么续号、
历史高水位怎么回灌闸门、过期怎么按量回收，都还没有。

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改，必须原样全绿）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 发放续期归还、脚本对拍、记号闸门
python3 -m unittest discover -s tests -v # 行为基线测试
python3 -m leasekeeper.bench             # 连环吞吐对比表
```

## 实现说明

- `leasekeeper/durable.py` 新增 `DurableKeeper`，语义与 `LeaseKeeper` 一致，老调用不动；过期只认注入钟，外面再套 `MonotonicClamp`（`clock.py`），NTP 回拨被钳在原地，租约不多活。
- 幂等发放：`grant(..., request_id=...)`，请求标识跟着重试走，租约活着期间同一标识（含并发重试）拿回同一份租约，不重复发号。
- 记号只增：grant 先追加日志并 fsync 再发号，崩溃重启从日志续号；各资源历史高水位随发放灌进 `FenceGuard`，重启先回灌再放行，旧记号过不了存储层。
- 重启那刻没归还的租约一律按回收处理（单调钟跨进程不可比，留着判不了期），恢复时计入 reclaims，同资源不会有两份活租约。
- 续期走 lease_id 直索引加到期小顶堆，纯内存 O(1) 不碰盘；`sweep` 只弹出当轮真到期的条目，开销与全表规模无关。
- `leasekeeper/dscript.py` 把并发重试（burst）与崩溃重启（crash）编进确定性脚本对拍；`bench` 登记 durable 实现并补两万租约下的巡检耗时对比。
