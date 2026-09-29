"""cronix 的基线调度实现。

现状是最朴素的一版：一条表达式只有一个分钟字段，且只能是单个整数。
到了那个分钟就算命中，没有范围、步长、列表，没有多字段，也没有下次
触发计算。

时间一律由外部传入（注入时钟），本模块不读取真实时间。
"""


class Scheduler:
    """只认识固定分钟整点的调度器。

    表达式是单个整数，取值范围 0 到 59，表示整点里的第几分钟。
    """

    def __init__(self, expression):
        minute = self._parse_minute(expression)
        self.expression = expression
        self.minute = minute

    @staticmethod
    def _parse_minute(expression):
        text = str(expression).strip()
        if not text.isdigit():
            raise ValueError("expression must be a single minute number: %r" % (expression,))
        minute = int(text)
        if minute < 0 or minute > 59:
            raise ValueError("minute out of range 0..59: %d" % minute)
        return minute

    def match(self, moment):
        """判断给定时刻是否命中。

        moment 是带 minute 属性的对象，只需读到分钟。命中即分钟相等。
        """
        return moment.minute == self.minute

    def describe(self):
        """返回人类可读的描述。"""
        return "at minute %d" % self.minute
