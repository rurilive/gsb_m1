"""宽度与换行：纯函数，唯一的宽度缓存也收口在本模块。"""

_WIDTH_CACHE = {}


def text_width(s):
    """显示宽度（纯函数）。历史口径：按 len() 算，中文也按 1 个宽。"""
    return len(s)


def cached_text_width(s):
    """text_width 的缓存版。全包唯一的缓存点，别在别处另开缓存。"""
    if s in _WIDTH_CACHE:
        return _WIDTH_CACHE[s]
    w = text_width(s)
    _WIDTH_CACHE[s] = w
    return w


def wrap_text(text, wrap):
    """把单元格文本切成若干行。wrap<=0 不换行。

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
        while cached_text_width(word) > wrap:
            if cur != "":
                lines.append(cur)
                cur = ""
            lines.append(word[0:wrap])
            word = word[wrap:]
        if cur == "":
            cur = word
        elif cached_text_width(cur) + 1 + cached_text_width(word) <= wrap:
            cur = cur + " " + word
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines
