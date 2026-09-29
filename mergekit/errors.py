"""mergekit 的错误体系。

当前 diff 只用到基类与 DiffError；编辑脚本、三方合并与策略注入补齐后，
会用上输入超限、合并冲突与策略非法的几种具体错误。
"""


class MergeKitError(Exception):
    """mergekit 全部错误的基类。"""


class DiffError(MergeKitError):
    """双向比较的输入不合法。"""


class InputLimitError(MergeKitError):
    """编辑脚本的动态规划规模超过配置上限。"""


class MergeConflictError(MergeKitError):
    """三方合并中出现了无法自动解决的冲突。"""


class StrategyError(MergeKitError):
    """冲突解决策略不合法。"""


__all__ = [
    "DiffError",
    "InputLimitError",
    "MergeConflictError",
    "MergeKitError",
    "StrategyError",
]
