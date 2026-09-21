"""计数口径集中放这里，缓存本体和参考实现都按这一套报数。"""

from collections import namedtuple

# hits/misses 只数 get 的结果；puts 数 put 调用；deletes 数真删掉的次数；
# live 是当前键数。put 覆盖已有键不算命中。
Stats = namedtuple("Stats", "hits misses evictions puts deletes live")


def hit_rate(stats):
    """命中率；一次 get 都没有时按 0 算。"""
    total = stats.hits + stats.misses
    if total == 0:
        return 0.0
    return stats.hits / total
