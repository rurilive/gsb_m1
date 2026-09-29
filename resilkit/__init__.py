"""resilkit: 可失败调用的重试执行器。"""

from .executor import Executor, RetryExhausted

__all__ = ["Executor", "RetryExhausted"]