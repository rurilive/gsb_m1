"""数字字面量在解析结果里的包装。"""


class Num:
    """一个 JSON 数字。

    text 是字面量原文，value 是按原文解析出来的数。
    """

    __slots__ = ("text", "value")

    def __init__(self, text):
        self.text = text
        self.value = float(text)

    def __int__(self):
        return int(self.value)

    def __float__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, Num):
            return self.text == other.text
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return hash(self.text)

    def __repr__(self):
        return "Num(%r)" % (self.text,)

    def __str__(self):
        return self.text
