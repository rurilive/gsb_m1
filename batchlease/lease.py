"""选主后的进程内租约管理。

成员表记录节点及其优先级，变更时代数递增；管理器按优先级选出
主节点，各节点为自己申请租约，一个节点可以先后持有多段租约，
对外可见的到期时间取各段里最晚的那个。
"""

import threading
import time


class LeaseError(Exception):
    """租约相关错误的基类。"""


class UnknownMember(LeaseError):
    """节点不在成员表里。"""

    def __init__(self, node):
        super().__init__("node %r is not a member" % (node,))
        self.node = node


class NoLease(LeaseError):
    """节点手上没有还能用的租约。"""

    def __init__(self, node):
        super().__init__("node %r holds no live lease" % (node,))
        self.node = node


class MembershipChanged(LeaseError):
    """批量操作期间成员表被增删过，整批不生效。"""

    def __init__(self, before, after):
        super().__init__(
            "membership changed during batch operation (generation %d -> %d)"
            % (before, after)
        )
        self.before = before
        self.after = after


class BatchReleaseResult:
    """批量释放的逐节点结果。

    released: 本次确实清掉了租约的节点。
    empty: 在表里但本来就没持有租约的节点。
    unknown: 不在成员表里的节点。
    """

    def __init__(self, released=(), empty=(), unknown=()):
        self.released = list(released)
        self.empty = list(empty)
        self.unknown = list(unknown)

    def __repr__(self):
        return ("BatchReleaseResult(released=%r, empty=%r, unknown=%r)"
                % (self.released, self.empty, self.unknown))


class MemberTable:
    """成员表：节点名到优先级，增删都会让代数加一。

    generation 用来给外部一个廉价的“表有没有被人动过”的判断，
    初始成员算第 0 代。
    """

    def __init__(self, members=None):
        self._members = {}
        self._generation = 0
        for node, priority in dict(members or {}).items():
            self._members[node] = priority

    def add(self, node, priority=0):
        """加入或更新一个成员，优先级没变就不算变更。"""
        if node in self._members and self._members[node] == priority:
            return False
        self._members[node] = priority
        self._generation += 1
        return True

    def remove(self, node):
        """移出一个成员，返回是否真的移掉了。"""
        if node in self._members:
            del self._members[node]
            self._generation += 1
            return True
        return False

    def generation(self):
        """当前代数，每次有效增删加一。"""
        return self._generation

    def nodes(self):
        """全部成员名，按字典序排好。"""
        return sorted(self._members)

    def priority(self, node):
        """节点的优先级，不在表里就抛 UnknownMember。"""
        if node not in self._members:
            raise UnknownMember(node)
        return self._members[node]

    def __contains__(self, node):
        return node in self._members

    def __len__(self):
        return len(self._members)


class LeaseManager:
    """按成员表选主、发放与回收租约。

    members: 初始成员表，形如 {节点名: 优先级}。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    default_ttl: renew 和 acquire 不带 ttl 时使用的租期秒数。
    """

    def __init__(self, members=None, clock=time.monotonic, default_ttl=30.0):
        self._table = MemberTable(members)
        self._clock = clock
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        # 节点 -> 段落列表，每段是 [起点, 到期时刻]
        self._segments = {}

    @property
    def table(self):
        """底层成员表，调用方可以直接增删成员。"""
        return self._table

    def primary(self):
        """选主：优先级最高的节点，同优先级取名字最小的，空表返回 None。"""
        nodes = self._table.nodes()
        if not nodes:
            return None
        return min(nodes, key=lambda n: (-self._table.priority(n), n))

    def _require_member(self, node):
        if node not in self._table:
            raise UnknownMember(node)

    def acquire(self, node, ttl=None):
        """为节点追加一段租约，返回到期时刻。

        ttl 省略时用 default_ttl；已有租约不覆盖，新段落叠在后面。
        """
        ttl = self._default_ttl if ttl is None else ttl
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        with self._lock:
            self._require_member(node)
            now = self._clock()
            end = now + ttl
            self._segments.setdefault(node, []).append([now, end])
            return end

    def renew(self, node):
        """把节点最后一段租约从当前时刻起续期，返回新的到期时刻。

        手上那段已经过期、或者根本没申请过，都算没有可用租约。
        """
        with self._lock:
            self._require_member(node)
            now = self._clock()
            segments = self._segments.get(node)
            if not segments or segments[-1][1] <= now:
                raise NoLease(node)
            segments[-1][1] = now + self._default_ttl
            return segments[-1][1]

    def release(self, node):
        """清掉节点的全部租约，返回之前是否持有。"""
        with self._lock:
            self._require_member(node)
            return self._segments.pop(node, None) is not None

    def merge(self, node):
        """合并节点手上相邻、重叠或首尾相接的段落，返回合并后的快照。

        按起点排序后，下一段起点不晚于当前段到期时刻（含相等）即并为一段；
        合并段的到期时刻取被并入各段里最晚的，不会凭空变长。
        """
        with self._lock:
            self._require_member(node)
            merged = []
            for start, end in sorted(self._segments.get(node, [])):
                if merged and start <= merged[-1][1]:
                    if end > merged[-1][1]:
                        merged[-1][1] = end
                else:
                    merged.append([start, end])
            if merged:
                self._segments[node] = merged
            else:
                self._segments.pop(node, None)
            return [(s, e) for s, e in merged]

    def acquire_batch(self, nodes, ttl=None):
        """原子地给一组节点各发一段租约，返回 {节点: 到期时刻}。

        任何一个节点不是成员、ttl 非法、节点重复，或申请过程中成员表
        被增删过，整批作废：不留下任何一段新租约。
        """
        ttl = self._default_ttl if ttl is None else ttl
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        targets = list(nodes)
        if len(set(targets)) != len(targets):
            raise ValueError("duplicate nodes in batch")
        with self._lock:
            before = self._table.generation()
            for node in targets:
                self._require_member(node)
            now = self._clock()
            if self._table.generation() != before:
                raise MembershipChanged(before, self._table.generation())
            end = now + ttl
            added = {node: [now, end] for node in targets}
            for node, segment in added.items():
                self._segments.setdefault(node, []).append(segment)
            after = self._table.generation()
            if after != before:
                for node, segment in added.items():
                    segs = self._segments.get(node)
                    if segs is not None:
                        try:
                            segs.remove(segment)
                        except ValueError:
                            pass
                        if not segs:
                            del self._segments[node]
                raise MembershipChanged(before, after)
            return {node: end for node in targets}

    def release_batch(self, nodes):
        """逐节点释放，个别失败不拖停整批，返回 BatchReleaseResult。

        已经释放成功的节点不会因为后面的节点出错而回滚；不在成员表的
        节点记到 unknown，在表里但本来就空着的记到 empty。
        """
        result = BatchReleaseResult()
        for node in dict.fromkeys(nodes):
            try:
                if self.release(node):
                    result.released.append(node)
                else:
                    result.empty.append(node)
            except UnknownMember:
                result.unknown.append(node)
        return result

    def segments(self, node):
        """节点手上的租约段落快照，每段是 (起点, 到期时刻)。"""
        with self._lock:
            self._require_member(node)
            return [(s, e) for s, e in self._segments.get(node, [])]

    def expires_at(self, node):
        """节点租约里最晚的到期时刻，没有租约返回 None。"""
        with self._lock:
            self._require_member(node)
            ends = [e for _, e in self._segments.get(node, [])]
            return max(ends) if ends else None

    def held(self, node):
        """节点是否持有尚未到期的租约。"""
        with self._lock:
            self._require_member(node)
            now = self._clock()
            return any(e > now for _, e in self._segments.get(node, []))
