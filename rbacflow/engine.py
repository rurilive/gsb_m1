"""策略判定入口：继承解析、通配匹配、显式拒绝与决策解释。

判定口径（一条具体动作 a，查询角色 r）：

1. 从 r 沿父边向上的整张继承图里，所有直接写过能盖住 a 的模式的角色
   都是候选；菱形去重，距离取最近（r 自己距离 0）。
2. 先找拒绝：只要任何祖先行过能盖住 a 的 deny，结果就是拒绝。
3. 没有拒绝才看允许：最近祖先有能盖住 a 的 grant 才放行。
4. 多条规则都能命中时取最具体的：精确压通配、长前缀压短前缀、
   近亲压远亲（同模式看距离，同距离按父边声明序取先到者）。

性能上不做全链展开：按 (模式, 角色) 记忆化“最近的直接持有者”，
沿父边向上只在首次访问时走一遍；规则一变，对应模式的记忆当场失效，
继承图一变，全部记忆失效。
"""

from collections import namedtuple

from .actions import candidates, validate


Decision = namedtuple("Decision",
                      ("kind", "pattern", "source", "distance", "match"))


class Explanation(object):
    """explain 的结果：结论加依据。

    布尔含义与 check 一致（bool(explain(...)) 就是判不判得过）；
    as_dict() 给全部字段。命中拒绝/允许时带模式、来源角色、到来源的
    继承链和匹配类型；没有任何命中时 kind 是 "default"。
    """

    __slots__ = ("allowed", "kind", "pattern", "source", "distance",
                 "path", "match", "reason")

    def __init__(self, allowed, kind, reason, pattern=None, source=None,
                 distance=None, path=None, match=None):
        self.allowed = allowed
        self.kind = kind
        self.reason = reason
        self.pattern = pattern
        self.source = source
        self.distance = distance
        self.path = path
        self.match = match

    def as_dict(self):
        return {
            "allowed": self.allowed,
            "kind": self.kind,
            "pattern": self.pattern,
            "source": self.source,
            "distance": self.distance,
            "path": list(self.path) if self.path is not None else None,
            "match": self.match,
            "reason": self.reason,
        }

    def keys(self):
        return self.as_dict().keys()

    def __getitem__(self, key):
        return self.as_dict()[key]

    def __bool__(self):
        return bool(self.allowed)

    def __str__(self):
        return self.reason

    def __repr__(self):
        return "Explanation(%s)" % (self.reason,)


class Engine(object):
    """对着一个 PolicyStore 做判定。

    store 里改授予、拒绝或继承，下一次判定马上看得到（按版本号失效缓存）。
    """

    def __init__(self, store):
        self.store = store
        self._grant_memo = {}   # 模式 -> {"version": int, "resolved": {...}}
        self._deny_memo = {}
        self._grant_graph_version = -1
        self._deny_graph_version = -1

    def check(self, role, action):
        """角色能不能做这个动作：有拒绝就拒绝，否则看允许。

        角色没声明抛 UnknownRole，动作名不合法抛 InvalidAction。
        """
        validate(action)
        self.store._require(role)
        return self._decide(role, action).kind == "allow"

    def check_many(self, role, actions):
        """一次判一批动作，返回动作到布尔值的字典，保持传入顺序。"""
        return {action: self.check(role, action) for action in actions}

    def permitted(self, role):
        """角色直接拿到的全部动作模式，按授予顺序（不展开继承与通配）。"""
        return self.store.granted(role)

    def explain(self, role, action):
        """给结论和依据，返回 Explanation。

        被拒时说清是哪条 deny、从哪个角色沿继承带上来的；放行时给出
        命中的 grant；两边都没命中给出默认拒绝。角色没声明抛
        UnknownRole，动作名不合法抛 InvalidAction。
        """
        validate(action)
        self.store._require(role)
        decision = self._decide(role, action)
        path = None
        if decision.source is not None:
            if decision.distance == 0:
                path = (decision.source,)
            else:
                path = self._shortest_path(role, decision.source)
        return self._make_explanation(role, action, decision, path)

    # ---- 决策 ----

    def _decide(self, role, action):
        """返回 Decision。候选模式按具体程度从高到低，deny 整体优先。"""
        shapes = candidates(action)
        for pattern in shapes:
            source, distance = self._resolve(role, pattern, denied=True)
            if source is not None:
                return Decision("deny", pattern, source, distance,
                                self._match_kind(pattern))
        for pattern in shapes:
            source, distance = self._resolve(role, pattern, denied=False)
            if source is not None:
                return Decision("allow", pattern, source, distance,
                                self._match_kind(pattern))
        return Decision("default", None, None, None, None)

    @staticmethod
    def _match_kind(pattern):
        return "wildcard" if (pattern == "*" or pattern.endswith(":*")) \
            else "exact"

    # ---- 缓存同步 ----

    def _resolve(self, role, pattern, denied):
        """找 role 继承图里直接持有 pattern 的最近角色。

        返回 (持有者, 距离)，没人持有返回 (None, None)。结果按
        (模式, 角色) 记忆；显式栈 DFS，千级深链也不炸栈。同距离时
        父边按 inherit 声明序先到先得，菱形天然去重。
        """
        memo = self._sync(denied, pattern)
        resolved = memo["resolved"]
        if role in resolved:
            return resolved[role]
        holders = self.store._denials if denied else self.store._grants

        # 栈帧：[节点, 父角色列表, 下一个父的下标, 最近距离, 最近持有者]
        active = {role}
        frames = [[role, list(self.store._parents[role]), 0, None, None]]
        while frames:
            frame = frames[-1]
            node, parents, index = frame[0], frame[1], frame[2]

            if index == 0 and pattern in holders[node]:
                resolved[node] = (node, 0)
                frames.pop()
                active.discard(node)
                if frames:
                    self._fold(frames[-1], node, 1)
                continue

            if index < len(parents):
                parent = parents[index]
                frame[2] += 1
                if parent in resolved:
                    holder, holder_distance = resolved[parent]
                    if holder is not None:
                        self._fold(frame, holder, holder_distance + 1)
                    continue
                if parent in active:
                    # DAG 下走不到这里，防御性跳过（继承边已保证无环）。
                    continue
                active.add(parent)
                frames.append(
                    [parent, list(self.store._parents[parent]), 0, None, None])
                continue

            holder = frame[4]
            distance = frame[3]
            resolved[node] = (holder, distance) if holder is not None \
                else (None, None)
            frames.pop()
            active.discard(node)
            if frames and holder is not None:
                self._fold(frames[-1], holder, distance + 1)

        return resolved[role]

    @staticmethod
    def _fold(frame, holder, distance):
        """把一个子结果（距离 distance 处是 holder）并入当前帧，近亲优先。"""
        if frame[3] is None or distance < frame[3]:
            frame[3] = distance
            frame[4] = holder

    def _sync(self, denied, pattern):
        """拿到模式对应的记忆表，规则或继承图一变就清。"""
        if denied:
            memos, tracker_attr, version_of = (
                self._deny_memo, "_deny_graph_version",
                self.store.deny_version)
        else:
            memos, tracker_attr, version_of = (
                self._grant_memo, "_grant_graph_version",
                self.store.grant_version)
        memo = memos.get(pattern)
        version = version_of(pattern)
        if memo is None:
            memo = {"version": version, "resolved": {}}
            memos[pattern] = memo
        elif memo["version"] != version:
            memo["version"] = version
            memo["resolved"].clear()
        graph_version = self.store.graph_version()
        if getattr(self, tracker_attr) != graph_version:
            # 图变了：清掉本侧全部模式的解析结果（只在变更后第一次判定时走）
            for entry in memos.values():
                entry["resolved"].clear()
            setattr(self, tracker_attr, graph_version)
        return memo

    # ---- 解释辅助 ----

    def _shortest_path(self, role, source):
        """沿父边 BFS 找 role 到 source 的最短链（explain 用，不进热路径）。"""
        queue = [role]
        previous = {role: None}
        head = 0
        while head < len(queue):
            current = queue[head]
            head += 1
            for parent in self.store._parents[current]:
                if parent in previous:
                    continue
                previous[parent] = current
                if parent == source:
                    path = [parent]
                    node = current
                    while node is not None:
                        path.append(node)
                        node = previous[node]
                    return tuple(reversed(path))
                queue.append(parent)
        return (role, source)

    def _make_explanation(self, role, action, decision, path):
        pattern = decision.pattern
        source = decision.source
        distance = decision.distance

        if decision.kind == "deny":
            via = ""
            if distance:
                via = "，由 %s 经继承链 %s 带到（链长 %d）" % (
                    source, " -> ".join(path), distance)
            reason = ("拒绝 %s：角色 %s 上的 deny %s 命中%s；"
                      "显式拒绝压过一切允许" % (action, source, pattern, via))
            return Explanation(False, "deny", reason, pattern=pattern,
                               source=source, distance=distance, path=path,
                               match=decision.match)

        if decision.kind == "allow":
            via = ""
            if distance:
                via = "，由 %s 经继承链 %s 带到（链长 %d）" % (
                    source, " -> ".join(path), distance)
            reason = "允许 %s：角色 %s 上的 grant %s 命中%s" % (
                action, source, pattern, via)
            return Explanation(True, "allow", reason, pattern=pattern,
                               source=source, distance=distance, path=path,
                               match=decision.match)

        reason = "拒绝 %s：%s 及其祖先没有任何授予覆盖此动作（默认拒绝）" % (
            action, role)
        return Explanation(False, "default", reason)
