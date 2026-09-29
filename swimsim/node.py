"""节点与静态成员表。

当前能力只有一层：一张由成员名到 MemberRecord 的静态表，加上整表广播。
节点不主动做任何探测，成员是否存活完全取决于调用方喂进来的观察，节点之
间也没有任何状态合并的口径。心跳与失败探测、怀疑态、版本化传播、反熵与
故障恢复都留待在这个基础上补齐。
"""

from .errors import DefinitionError, UnknownMember
from .member import MemberRecord


class Node:
    """一个成员协议节点的静态视图。

    name 是本节点自己的名字，clock 是可注入的逻辑时钟，缺省用 0 起的
    时钟；members 是初始成员名集合。
    """

    def __init__(self, name, members=(), clock=None):
        if not isinstance(name, str) or not name:
            raise DefinitionError("节点名必须是非空字符串: %r" % (name,))
        if clock is None:
            from .clock import ManualClock
            clock = ManualClock()
        self._name = name
        self._clock = clock
        self._members = {}
        for member in members:
            self.add_member(member)

    @property
    def name(self):
        """本节点的名字。"""
        return self._name

    @property
    def clock(self):
        """本节点使用的逻辑时钟。"""
        return self._clock

    def add_member(self, name, alive=True):
        """把一个成员加进静态成员表。

        成员名必须是非空字符串，重复加入在定义期 fail-fast 抛
        DefinitionError，返回自身以便链式调用。
        """
        if not isinstance(name, str) or not name:
            raise DefinitionError("成员名必须是非空字符串: %r" % (name,))
        if name in self._members:
            raise DefinitionError("成员重复加入: %r" % (name,))
        self._members[name] = MemberRecord(name, alive, self._clock.now)
        return self

    def known(self):
        """当前成员表里的成员名，排序后返回。"""
        return tuple(sorted(self._members))

    def has(self, member):
        """成员表里是否有这个成员。"""
        return member in self._members

    def record(self, member):
        """取一个成员的记录，不在表里抛 UnknownMember。"""
        try:
            return self._members[member]
        except KeyError:
            raise UnknownMember("未知成员: %r" % (member,))

    def is_alive(self, member):
        """成员当前是否被标记为存活。"""
        return self.record(member).alive

    def observe(self, member, alive=True):
        """按一次外部观察更新成员记录，返回刷新后的记录。

        观察只改写存活标志与最近被看见的时间，不改写别的维度；这一侧把
        存活标志当作普通布尔直接落下来。
        """
        self.record(member)
        record = MemberRecord(member, alive, self._clock.now)
        self._members[member] = record
        return record

    def gossip(self, member):
        """把当前成员表打成一个可外发的快照。

        成员名排序后逐条序列化，返回一个列表；这是节点之间唯一的数据交换
        形式，不带任何协议元数据。
        """
        self.record(member)
        return [r.snapshot() for r in self._sorted_records()]

    def merge(self, snapshot):
        """按时间先后合并一张对端快照。

        同一成员只有在快照里的 last_seen 严格更大时才覆盖本地，时间相同时
        保留本地；快照里出现本地未知的成员，直接补进成员表。
        """
        if not isinstance(snapshot, (list, tuple)):
            raise DefinitionError("快照必须是列表或元组: %r" % (snapshot,))
        for entry in snapshot:
            try:
                name = entry["name"]
                alive = entry["alive"]
                last_seen = entry["last_seen"]
            except (TypeError, KeyError):
                raise DefinitionError("快照条目缺字段: %r" % (entry,))
            if name not in self._members:
                self.add_member(name, alive)
                self._members[name] = MemberRecord(name, alive, last_seen)
                continue
            current = self._members[name]
            if last_seen > current.last_seen:
                self._members[name] = MemberRecord(name, alive, last_seen)
        return self

    def _sorted_records(self):
        return [self._members[name] for name in sorted(self._members)]

    def __repr__(self):
        return "<Node %s members=%d>" % (self._name, len(self._members))