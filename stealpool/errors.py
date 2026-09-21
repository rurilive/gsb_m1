"""stealpool 的异常类型。"""


class StealPoolError(Exception):
    """本库所有异常的基类。"""


class PoolClosed(StealPoolError):
    """池已关闭，不能再提交任务。"""


class TaskCancelled(StealPoolError):
    """任务在开始执行之前被取消，取结果时抛出。"""
