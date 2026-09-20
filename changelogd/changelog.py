"""按版本号记录字段变更的变更日志。

每个对象维护一串变更记录：append 追加，history 取全文，
at 把某一版本之前的变更叠成对象快照。纯标准库，无真实 IO。
"""

import time
from collections import namedtuple

# 一条字段变更：哪个对象的哪个字段，在哪个版本被改成了什么值。
Change = namedtuple("Change", ["obj", "field", "value", "version", "ts"])


class ChangeLog:
    """单条时间线上的字段变更日志。

    clock: 返回当前时刻的可调用对象，默认 time.time，测试可注入。
    version 由调用方给定，本包不校验它是否单调。
    """

    def __init__(self, clock=time.time):
        self._clock = clock
        self._entries = {}  # obj -> [Change]，保持 append 顺序

    def append(self, obj, field, value, version):
        """给 obj 的 field 记一条变更，返回新记录。"""
        change = Change(obj, field, value, version, self._clock())
        self._entries.setdefault(obj, []).append(change)
        return change

    def history(self, obj):
        """obj 的全部变更，按 append 顺序，返回新列表。"""
        return list(self._entries.get(obj, ()))

    def at(self, obj, version):
        """重建 obj 在给定版本的快照。

        每个字段取 append 顺序里最后一条 version 不超过给定值的变更；
        在此之前该字段没有变更则不出现。返回新 dict。
        """
        snapshot = {}
        for change in self._entries.get(obj, ()):
            if change.version <= version:
                snapshot[change.field] = change.value
        return snapshot

    def objects(self):
        """出现过的对象名，按首次 append 顺序。"""
        return list(self._entries)
