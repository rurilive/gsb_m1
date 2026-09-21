"""leasekeeper: 调度平台的租约发放包。

LeaseKeeper 是内存基线：按资源发放、续期、归还、清扫租约，记号只增；
DurableLeaseKeeper 加幂等发号、日志恢复与按到期槽回收；FenceGuard 是
存储层挡旧记号的闸门；FakeClock 供测试手动拨时间；script 提供确定性
脚本与纯模型对拍（含并发重试、崩溃重启）；bench 量吞吐与巡检开销。纯
标准库，无外部依赖。
"""

from leasekeeper.clock import FakeClock
from leasekeeper.durable import DurableLeaseKeeper
from leasekeeper.fence import FenceGuard, StaleFence
from leasekeeper.journal import FileJournal, MemoryJournal
from leasekeeper.keeper import KeeperStats, Lease, LeaseConflict, LeaseKeeper
from leasekeeper.script import (
    as_tuple,
    drive,
    drive_durable,
    make_durable_script,
    make_script,
    model_durable,
    model_run,
)
from leasekeeper.wheel import ExpiryWheel

__all__ = [
    "DurableLeaseKeeper",
    "ExpiryWheel",
    "FakeClock",
    "FileJournal",
    "FenceGuard",
    "KeeperStats",
    "Lease",
    "LeaseConflict",
    "LeaseKeeper",
    "MemoryJournal",
    "StaleFence",
    "as_tuple",
    "drive",
    "drive_durable",
    "make_durable_script",
    "make_script",
    "model_durable",
    "model_run",
]
