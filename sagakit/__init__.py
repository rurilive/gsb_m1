"""sagakit：saga 编排器的起点，纯标准库。

当前只导出基线的顺序步骤执行器；补偿、重试、超时、
幂等与状态恢复等能力见任务描述。
"""

from .runner import StepRunner

__all__ = ["StepRunner"]
