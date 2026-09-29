"""planopt: 内存查询执行与优化的雏形。

现状只有一张行式表与一个朴素执行器，见 planopt/table.py 与 planopt/exec.py。
逻辑计划、等价重写、代价模型、连接顺序与计划解释见任务描述。
"""

from planopt.table import Table
from planopt.exec import ExecStats, Join, Query, execute

__all__ = ["Table", "Join", "Query", "ExecStats", "execute"]
