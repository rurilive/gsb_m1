"""nestrun 的异常类型。"""


class SchedulerError(Exception):
    """调度器相关错误的基类。"""


class InvalidTransition(SchedulerError):
    """非法的状态转换。"""

    def __init__(self, current, target):
        super().__init__("illegal transition: {} -> {}".format(current, target))
        self.current = current
        self.target = target


class Cancelled(SchedulerError):
    """任务因取消而落定时，写进 task.error 的原因对象。"""

    def __init__(self, reason="cancelled"):
        super().__init__(reason)
        self.reason = reason
