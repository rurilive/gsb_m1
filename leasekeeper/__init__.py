"""leasekeeper: 调度平台的租约发放包。

LeaseKeeper 按资源发放、续期、归还、清扫租约，记号只增；DurableKeeper
加幂等发放、日志续号与按到期回收；FenceGuard 是存储层挡旧记号的闸门；
FakeClock 供测试手动拨时间，MonotonicClamp 钳住回拨；script 与 dscript
提供确定性脚本与纯模型对拍；bench 量吞吐。纯标准库，无外部依赖。
"""

from leasekeeper.clock import FakeClock, MonotonicClamp
from leasekeeper.dscript import (
    as_dtuple,
    drive_durable,
    make_dscript,
    model_durable,
)
from leasekeeper.durable import DurableKeeper
from leasekeeper.fence import FenceGuard, StaleFence
from leasekeeper.keeper import KeeperStats, Lease, LeaseConflict, LeaseKeeper
from leasekeeper.script import as_tuple, drive, make_script, model_run

__all__ = [
    "DurableKeeper",
    "FakeClock",
    "FenceGuard",
    "KeeperStats",
    "Lease",
    "LeaseConflict",
    "LeaseKeeper",
    "MonotonicClamp",
    "StaleFence",
    "as_dtuple",
    "as_tuple",
    "drive",
    "drive_durable",
    "make_dscript",
    "make_script",
    "model_durable",
    "model_run",
]
