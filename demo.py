"""cronix 现状演示。

第一段：用最朴素的整分调度器，设一个整分表达式，判断某个时刻是否命中。
第二段：预留给完整 cron 解析与求值的演示位子（见文末注释）。
"""

from cronix.schedule import Scheduler


class _Moment(object):
    """演示用时刻对象，只带分钟。"""

    def __init__(self, minute):
        self.minute = minute


def main():
    print("=== 整分调度器（基线）===")
    scheduler = Scheduler(30)
    print("  表达式 -> %s" % scheduler.describe())
    print("  第 30 分命中 -> %s" % scheduler.match(_Moment(30)))
    print("  第 29 分命中 -> %s" % scheduler.match(_Moment(29)))

    # TODO(完整 cron 改造): 现在表达式只认单个分钟整数。把 cronix 扩成能解析
    # 五字段（分、时、日、月、星期）的完整 cron 表达式，支持星号、单值、范围、
    # 步长、列表及其组合，解析成字段集合，给定注入时刻判断是否命中，算出下次
    # 触发时点并能展开区间内全部触发时点，日与星期按或逻辑组合，越界值、非法
    # 步长、字段个数不对、未支持的宏名一律 fail fast 抛异常（异常继承 CronError
    # 基类）之后，在这里补一段演示：先解析一条带范围与步长的表达式并打印各字段
    # 集合，再判断几个边界时刻是否命中，最后从某个时刻算出下次触发时点并展开
    # 接下来几个触发时点打印出来，与逐分钟推进的结果对照一致。


if __name__ == "__main__":
    main()
