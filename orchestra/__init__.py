"""orchestra：一个通用流程编排器，纯标准库，无外部依赖。

当前对外能力是 Runner：登记若干具名步骤，按登记顺序串行执行。分支选择、
并行汇聚、补偿事务、步骤状态机、检查点重入与超时都留待在这个基础上补齐。
"""

from .errors import (
    CycleError,
    DefinitionError,
    DuplicateStep,
    InvalidStepName,
    OrchestraError,
    RunError,
    StateError,
    StepFailed,
    StepNotFound,
    StepTimeout,
)
from .pipeline import Pipeline
from .runner import Runner, require_step

__all__ = [
    "CycleError",
    "DefinitionError",
    "DuplicateStep",
    "InvalidStepName",
    "OrchestraError",
    "Pipeline",
    "RunError",
    "Runner",
    "StateError",
    "StepFailed",
    "StepNotFound",
    "StepTimeout",
    "require_step",
]