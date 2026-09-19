"""buildplan 的异常族。"""


class BuildPlanError(Exception):
    """本包所有错误的基类。"""


class ManifestError(BuildPlanError):
    """清单解析错误：语法不合法或目标重复。"""


class GraphError(BuildPlanError):
    """依赖图错误：未知依赖或依赖成环。"""
