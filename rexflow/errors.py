"""模式语法错误。"""


class PatternError(ValueError):
    """模式串写得不对时抛出。

    pos 是出错字符在模式串里的下标（从 0 起），调用方可以直接定位；
    pattern 是原始模式串，message 不带位置与模式文本，便于单独使用。
    """

    def __init__(self, message, pattern, pos):
        self.message = message
        self.pattern = pattern
        self.pos = pos
        pointer = " " * pos + "^"
        super().__init__(
            "%s，位置 %d\n%s\n%s" % (message, pos, pattern, pointer))
