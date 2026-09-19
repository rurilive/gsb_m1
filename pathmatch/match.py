"""段级 glob 匹配。"""

import re


def _segment_regex(segment):
    """把单个 pattern 段翻译成正则：* 不跨段，? 匹配单个字符。"""
    parts = []
    for ch in segment:
        if ch == "*":
            parts.append("[^/]*")
        elif ch == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def match(pattern, path):
    """段级 glob：两侧按 / 分段，段数一致且逐段命中才算匹配。

    * 匹配段内任意字符（不跨段），? 匹配段内单个字符，
    其余字符按字面处理，大小写敏感。
    """
    p_segs = pattern.split("/")
    t_segs = path.split("/")
    if len(p_segs) != len(t_segs):
        return False
    return all(
        re.fullmatch(_segment_regex(p), t) is not None
        for p, t in zip(p_segs, t_segs)
    )
