"""buildplan: 依赖图执行器。

清单解析 -> 拓扑分层 -> 按层模拟执行 -> 报告，纯标准库。
"""

from .errors import BuildPlanError, GraphError, ManifestError
from .executor import Executor, PlanReport, Record, Report, StageVisitor, target_cost_ms
from .graph import layer_targets
from .manifest import Manifest, Target, parse_manifest

__all__ = [
    "BuildPlanError",
    "GraphError",
    "ManifestError",
    "Executor",
    "PlanReport",
    "Record",
    "Report",
    "StageVisitor",
    "target_cost_ms",
    "layer_targets",
    "Manifest",
    "Target",
    "parse_manifest",
]
