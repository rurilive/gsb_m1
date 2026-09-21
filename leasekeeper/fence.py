"""记号闸门：存储层按记号挡旧持有者的最后防线。

租约台发的记号跟着写请求走，闸门给每个资源记一个见过的最大记号：记号
不小于最大值放行，比最大值小的挡下抛 StaleFence。seal 用来把历史高水
位灌回来，进程重启或换库时先灌再放行，旧纪元的记号就再也进不来。
"""

import threading


class StaleFence(Exception):
    """记号落后于该资源已见过的最大值，这笔写被挡下。"""


class FenceGuard:
    """按资源记最大记号的写闸门，记号从 1 起算。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._high = {}

    def check(self, resource, token):
        """放行返回 True；token 比该资源已见最大值小抛 StaleFence。

        与最大值相等的记号放行，同一笔写的重试重放不算旧。
        """
        token = _as_token(token)
        with self._lock:
            high = self._high.get(resource, 0)
            if token < high:
                raise StaleFence(
                    "stale token %d behind high water %d on %r"
                    % (token, high, resource)
                )
            if token > high:
                self._high[resource] = token
            return True

    def seal(self, resource, high_water):
        """把历史高水位灌到 resource 上，之后更小的记号过不去。

        高水位只涨不降，灌个更小的值不动原状，返回灌完后的高水位。
        """
        high_water = _as_token(high_water)
        with self._lock:
            current = self._high.get(resource, 0)
            if high_water > current:
                self._high[resource] = high_water
            return self._high[resource]

    def high_water(self, resource):
        """该资源当前的最大记号，没见过的资源是 0。"""
        with self._lock:
            return self._high.get(resource, 0)


def _as_token(token):
    if not isinstance(token, int) or isinstance(token, bool):
        raise ValueError("token must be an int")
    if token < 1:
        raise ValueError("token must be positive")
    return token
