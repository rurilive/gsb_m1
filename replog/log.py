"""replog 的现状实现：一个最朴素的单机追加日志。

LocalLog 只按追加次序保存条目，索引从 1 开始；append 在末尾追加一条并返回
自增序号，按序号读回某条条目的任期，末尾可截断，另带一个已经列到哪儿的
提交位置标记。没有副本，没有复制，没有任期推进，也没有回退与覆盖，这些都
留待在这个基础上补齐。
"""


class RepLogError(Exception):
    """replog 所有可诊断错误的基类。

    调用方只捕捉 RepLogError 即可一次性接住所有错误，具体错误继承本类。
    复制、任期与选举、回退与覆盖相关的错误都留待在这一层之上扩展。
    """


class InvalidIndex(RepLogError):
    """序号非法：越界、为负或不是整数。"""


class UnknownNode(RepLogError):
    """未知副本：操作指向的副本不在本次模拟的副本集合里。"""


class Entry:
    """一条日志条目：序号、任期与命令。

    序号从 1 开始且连续，term 是产生这条条目的任期，command 是不透明的
    负载。
    """

    __slots__ = ("index", "term", "command")

    def __init__(self, index, term, command):
        self.index = index
        self.term = term
        self.command = command

    def __repr__(self):
        return "Entry(index=%r, term=%r, command=%r)" % (
            self.index,
            self.term,
            self.command,
        )


def _check_index(index, size, allow_end=False):
    """序号校验：必须是整数且落在 [1, size] 内，allow_end 时允许 size + 1。"""
    if isinstance(index, bool) or not isinstance(index, int):
        raise InvalidIndex("序号必须是整数，收到 %r" % (index,))
    upper = size + 1 if allow_end else size
    if index < 1 or index > upper:
        raise InvalidIndex("序号越界，收到 %r，当前日志长度 %d" % (index, size))
    return index


class LocalLog:
    """一个按追加次序排好的单机日志。

    序号从 1 开始，条目按追加次序保存。本类不感知副本之间的复制，也不做
    多数提交、任期推进与冲突回退。
    """

    def __init__(self):
        self._entries = []
        self._commit_index = 0

    def append(self, term, command):
        """在末尾追加一条条目并返回它的自增序号。"""
        index = len(self._entries) + 1
        entry = Entry(index, term, command)
        self._entries.append(entry)
        return index

    def get(self, index):
        """按序号读回一条条目，序号越界即报错。"""
        _check_index(index, len(self._entries))
        return self._entries[index - 1]

    def entries(self):
        """按序号次序返回全部条目的浅拷贝。"""
        return list(self._entries)

    def size(self):
        """当前日志长度。"""
        return len(self._entries)

    def last_index(self):
        """最后一条条目的序号，空日志为 0。"""
        return len(self._entries)

    def last_term(self):
        """最后一条条目的任期，空日志为 0。"""
        if not self._entries:
            return 0
        return self._entries[-1].term

    def term_at(self, index):
        """读取某序号处条目的任期，序号越界即报错。"""
        _check_index(index, len(self._entries))
        return self._entries[index - 1].term

    def truncate_from(self, index):
        """丢掉 index 及其之后的条目，返回被丢掉的条目。"""
        _check_index(index, len(self._entries), allow_end=True)
        dropped = self._entries[index - 1:]
        self._entries = self._entries[:index - 1]
        if self._commit_index >= index:
            self._commit_index = index - 1
        return dropped

    def commit_index(self):
        """当前已提交到的序号。"""
        return self._commit_index

    def reset(self):
        """清空全部条目。"""
        self._entries = []
        self._commit_index = 0
