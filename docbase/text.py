"""文本切分小工具。

库里的文档中英文混排，中文没有空格，这里只做最朴素的切分：
先把文本按字符类别切成连续的中文段与其它段，中文段按单字取词，
其它段按字母数字段取词并转小写，标点与空白直接丢掉。
"""

import re

_WORD_RE = re.compile(r"[a-z0-9]+")

# 中文常用的几个码位区段，够本库用。
_CJK_RANGES = (
    (0x3400, 0x4DBF),  # 扩展 A
    (0x4E00, 0x9FFF),  # 基本区
    (0xF900, 0xFAFF),  # 兼容区
)


def is_cjk(ch):
    """这个字符算不算中文。"""
    cp = ord(ch)
    for lo, hi in _CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def chunks(text):
    """把文本切成 (kind, segment) 列表，按出现顺序。

    kind 是 "cjk" 或 "other"；同类的连续字符归成一个 segment，
    标点、空白都会把中文段断开。
    """
    result = []
    kind = None
    start = 0
    for i, ch in enumerate(text):
        cur = "cjk" if is_cjk(ch) else "other"
        if cur != kind:
            if kind is not None:
                result.append((kind, text[start:i]))
            kind = cur
            start = i
    if kind is not None:
        result.append((kind, text[start:]))
    return result


def tokens(text):
    """当前口径：中文按单字，英文数字按段切并转小写。"""
    words = []
    for kind, segment in chunks(text.casefold()):
        if kind == "cjk":
            words.extend(segment)
        else:
            words.extend(_WORD_RE.findall(segment))
    return words
