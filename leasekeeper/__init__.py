"""leasekeeper: 调度平台的租约发放包。

LeaseKeeper 按资源发放、续期、归还、清扫租约，记号只增；FenceGuard 是
存储层挡旧记号的闸门；FakeClock 供测试手动拨时间；script 提供确定性
脚本与纯模型对拍；bench 量吞吐。纯标准库，无外部依赖。
"""

from leasekeeper.clock import FakeClock
from leasekeeper.fence import FenceGuard, StaleFence
from leasekeeper.keeper import KeeperStats, Lease, LeaseConflict, LeaseKeeper
from leasekeeper.script import as_tuple, drive, make_script, model_run

__all__ = [
    "FakeClock",
    "FenceGuard",
    "KeeperStats",
    "Lease",
    "LeaseConflict",
    "LeaseKeeper",
    "StaleFence",
    "as_tuple",
    "drive",
    "make_script",
    "model_run",
]
