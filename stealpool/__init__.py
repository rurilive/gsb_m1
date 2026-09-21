"""stealpool: 采集管线在用的进程内任务池。

固定线程数加一个全局队列，submit 提交任务返回 Future，
取结果、取消、运行统计都走 Pool 和 Future 上的方法。
任务树可以用 reference 里的顺序实现和 TreeRunner 对拍。
"""

from stealpool.errors import PoolClosed, StealPoolError, TaskCancelled
from stealpool.future import CANCELLED, FINISHED, PENDING, RUNNING, Future
from stealpool.pool import Pool, Stats
from stealpool.reference import TaskNode, TreeRunner, random_tree, run_sequential

__all__ = [
    "CANCELLED",
    "FINISHED",
    "Future",
    "PENDING",
    "Pool",
    "PoolClosed",
    "RUNNING",
    "Stats",
    "StealPoolError",
    "TaskCancelled",
    "TaskNode",
    "TreeRunner",
    "random_tree",
    "run_sequential",
]
