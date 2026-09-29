"""pather: 一个最朴素的点号路径取值器。

现状只有按点号逐级取字典键的 Getter，见 pather/getter.py。
数组下标、通配、过滤、递归下降与切片见任务描述。
"""

from pather.getter import Getter

__all__ = ["Getter"]
