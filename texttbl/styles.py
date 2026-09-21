"""texttbl.styles：边框样式表。

每套样式就是一张字符表（角/横/竖/交叉），render 不再 if/elif 分支。
加新样式 = 在 STYLES 里加一条记录，不用动渲染代码。
"""

from collections import namedtuple

# frame=False 的样式（markdown）不画上/下/分隔边框，只画竖线，
# 表头后固定输出 markdown 分隔行（横线数与列宽一致）。
Style = namedtuple(
    "Style",
    [
        "vertical",   # 列间竖线
        "horizontal", # 边框横线
        "top_left", "top_join", "top_right",
        "mid_left", "mid_join", "mid_right",
        "bot_left", "bot_join", "bot_right",
        "frame",              # 是否画上/下/表头分隔边框
        "header_separator",   # "border"（用 mid 边框）或 "markdown"（| --- |）
    ],
)

STYLES = {
    "ascii": Style(
        vertical="|", horizontal="-",
        top_left="+", top_join="+", top_right="+",
        mid_left="+", mid_join="+", mid_right="+",
        bot_left="+", bot_join="+", bot_right="+",
        frame=True, header_separator="border",
    ),
    "light": Style(
        vertical="│", horizontal="─",
        top_left="┌", top_join="┬", top_right="┐",
        mid_left="├", mid_join="┼", mid_right="┤",
        bot_left="└", bot_join="┴", bot_right="┘",
        frame=True, header_separator="border",
    ),
    "heavy": Style(
        vertical="┃", horizontal="━",
        top_left="┏", top_join="┳", top_right="┓",
        mid_left="┣", mid_join="╋", mid_right="┫",
        bot_left="┗", bot_join="┻", bot_right="┛",
        frame=True, header_separator="border",
    ),
    "markdown": Style(
        vertical="|", horizontal="-",
        top_left="", top_join="", top_right="",
        mid_left="", mid_join="", mid_right="",
        bot_left="", bot_join="", bot_right="",
        frame=False, header_separator="markdown",
    ),
}


def get_style(name):
    """按名字取样式表。未知样式在 render 时报错（历史行为）。"""
    try:
        return STYLES[name]
    except KeyError:
        raise ValueError("unknown style: %r" % (name,))
