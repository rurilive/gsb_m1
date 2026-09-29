"""现有的流式处理入口：逐条 for 循环。

run_stream 是当前唯一的处理函数，也是基线测试锁住的行为：
source 里的记录按顺序取出，逐条经 process 变换后交给 sink，返回 sink 的
累计结果；process 抛出的异常会一路冒泡并中断整个处理，之前已交给 sink 的
记录保留。
"""


def run_stream(source, process, sink, initial=None):
    """把 source 逐条经 process 处理后交给 sink。

    source 是可迭代对象，process 收一条记录返回一条记录，sink 收
    (累计值, 新值) 返回新的累计值。返回最终的累计值。
    """
    acc = initial
    for record in source:
        acc = sink(acc, process(record))
    return acc
