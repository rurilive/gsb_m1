"""pushrelabel：网络最大流与最小割，纯标准库，无外部依赖。

当前对外能力是一份朴素实现：在残量网络上反复做一次广度搜索找一条增广路，
沿路逐条推流，直到再也找不到增广路；最小割则按残量可达性直接读出。增广路
数量与容量有关，容量一大就要反复增广很多次。预流推进那种先沿源点所有出边
饱和推流、再靠高度标记与推流重标记把余流送回汇点的做法，以及对应的边界
覆盖与两条路径的逐项比对，都留待在这个基础上补齐。
"""

from .flow import (
    Edge,
    Erro,
    FlowNetwork,
    FlowResult,
    InvalidCapacityError,
    MinCutResult,
    NoPathError,
    NodeNotFoundError,
    SelfLoopError,
    SourceSinkError,
    max_flow,
    min_cut,
)

__all__ = [
    "Edge",
    "Erro",
    "FlowNetwork",
    "FlowResult",
    "InvalidCapacityError",
    "MinCutResult",
    "NoPathError",
    "NodeNotFoundError",
    "SelfLoopError",
    "SourceSinkError",
    "max_flow",
    "min_cut",
]
