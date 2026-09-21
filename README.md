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

- 新能力全在新模块：`durable.py` 的 `DurableLeaseKeeper` 与 `LeaseKeeper` 同构，老调用与 `tests/` 基线一字未动。
- 过期只认注入钟：`durable.py` 在内部对读数做单调钳制，时钟被往回拨时沿用上一次读到的时刻，旧租约不复活。
- `grant(..., request_id=)` 幂等：同标识（含并发重试、撞车请求、跨重启）拿回同一份结果；标识串用不同参数直接报错。
- grant/deny/release 先写 `journal.py` 的只追加日志（文件版每条 fsync）；`recover` 重放续号，未到期未归还的租约续活，过期即回收。
- 续期不进日志（万次/秒路径零磁盘），崩溃后按发号时的原始到期判活：宁可提前回收，同一资源也不会有两份活租约。
- 记号跨重启只增；每资源历史最大记号可经 `seal_guard` 灌回 `FenceGuard`，旧纪元记号被存储层挡下。
- `wheel.py` 把到期时刻量化进秒级槽位 + 非空槽小堆，`sweep` 开销只跟当轮到期条数走，与活跃总量无关。
- `script.py` 新增 `make_durable_script`/`drive_durable`/`model_durable`，把并发重试与崩溃重放编进确定性脚本对拍。
