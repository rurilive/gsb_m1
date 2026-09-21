"""texttbl.measure：宽度计算与文本换行，全部是纯函数。

缓存只在本模块内部使用（_WIDTH_CACHE），外部一律走 text_width()；
需要清缓存（比如测试）时调 clear_width_cache()，别直接摸 dict。
"""

_WIDTH_CACHE = {}


def text_width(s):
    """显示宽度。历史口径：按 len() 算，中文也按 1 个宽。"""
    if s in _WIDTH_CACHE:
        return _WIDTH_CACHE[s]
    w = len(s)
    _WIDTH_CACHE[s] = w
    return w


def clear_width_cache():
    """清空宽度缓存。缓存只影响性能，不影响结果。"""
    _WIDTH_CACHE.clear()


def wrap_text(text, wrap):
    """把文本切成若干行。wrap<=0 不换行。

    词间换行（连续空白当一个分隔），超长词硬切。历史口径，别改。
    """
    if wrap is None or wrap <= 0:
        return [text]
    tokens = text.split()
    if len(tokens) == 0:
        return [""]
    lines = []
    cur = ""
    for word in tokens:
        while text_width(word) > wrap:
            if cur != "":
                lines.append(cur)
                cur = ""
            lines.append(word[0:wrap])
            word = word[wrap:]
        if cur == "":
            cur = word
        elif text_width(cur) + 1 + text_width(word) <= wrap:
            cur = cur + " " + word
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines
