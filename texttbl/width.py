"""显示宽度计算：纯函数，无模块级可变状态。

历史口径：宽度按 len() 算，中文等宽字符也按 1 个宽。
缓存只在单次计算内部（functools.lru_cache）收口，外部拿到的
text_width 是纯函数：同入参永远同结果，谁都改不了全局状态。
"""

from functools import lru_cache


@lru_cache(maxsize=4096)
def _cached_width(text):
    return len(text)


def text_width(text):
    """单段文本的显示宽度（历史口径 == len）。纯函数。"""
    return _cached_width(text)


def column_widths(cells_by_col):
    """纯函数：cells_by_col 是每个列的 Cell 列表，返回各列宽度列表。

    宽度 = 全表（含表头）该列所有物理行的最大显示宽。
    不读、不写任何外部状态。
    """
    widths = []
    for cells in cells_by_col:
        w = 0
        for cell in cells:
            cell_w = max((text_width(line) for line in cell.lines), default=0)
            if cell_w > w:
                w = cell_w
        widths.append(w)
    return widths
