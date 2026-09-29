"""columnkit: 内存列式查询执行器。

当前只有一张行式表与最简单的谓词过滤，见 columnkit/table.py。
谓词下推、投影裁剪、哈希连接、聚合与执行计划解释见任务描述。
"""

from columnkit.table import Table, select

__all__ = ["Table", "select"]