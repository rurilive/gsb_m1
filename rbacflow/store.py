"""角色、授权、拒绝与继承关系的本地存放。

PolicyStore 是策略库的全部状态：角色、直接授予、直接拒绝、父子继承边。
判定本身不在这里，Engine 把它当唯一事实来源。

继承是有向无环图：inherit(child, parent) 加一条边，多父和菱形都允许，
但成环的声明当场抛 InheritanceCycle。
"""

from .actions import validate, validate_pattern
from .errors import (
    DuplicateDeny,
    DuplicateGrant,
    InheritanceCycle,
    NotGranted,
    PolicyError,
    UnknownRole,
)


class PolicyStore(object):
    """角色、授予、拒绝和继承边的总账。

    角色按声明先后排列；同一角色的授予/拒绝按写入先后排列；父角色按
    inherit 的先后排列。grant/deny/revoke 会推进对应模式的版本号，
    inherit 会推进图版本号，Engine 靠版本号让缓存即时失效。
    """

    def __init__(self):
        self._roles = []          # 角色名，声明序
        self._grants = {}         # 角色名 -> {模式: None}，授予序
        self._denials = {}        # 角色名 -> {模式: None}，拒绝序
        self._parents = {}        # 角色名 -> {父角色: None}，inherit 序
        self._children = {}       # 角色名 -> {子角色: None}
        self._grant_versions = {}   # 模式 -> 版本号
        self._deny_versions = {}    # 模式 -> 版本号
        self._graph_version = 0

    # ---- 角色 ----

    def declare(self, role):
        """声明一个角色；重复声明是空操作。"""
        if not isinstance(role, str) or not role:
            raise PolicyError("角色名必须是非空字符串: %r" % (role,))
        if role not in self._grants:
            self._roles.append(role)
            self._grants[role] = {}
            self._denials[role] = {}
            self._parents[role] = {}
            self._children[role] = {}

    def has_role(self, role):
        return role in self._grants

    def roles(self):
        """全部角色，按声明顺序。"""
        return list(self._roles)

    def _require(self, role):
        if role not in self._grants:
            raise UnknownRole("未声明的角色: %r" % (role,))

    # ---- 授予 ----

    def grant(self, role, action):
        """给角色直接授予一个动作模式（可以是 "pkg:*" 这样的尾部通配）。"""
        validate_pattern(action)
        self._require(role)
        owned = self._grants[role]
        if action in owned:
            raise DuplicateGrant("角色 %s 已经拿到过 %s" % (role, action))
        owned[action] = None
        self._grant_versions[action] = self._grant_versions.get(action, 0) + 1

    def revoke(self, role, action):
        """撤掉角色直接拿到的某个动作模式。"""
        self._require(role)
        owned = self._grants[role]
        if action not in owned:
            raise NotGranted("角色 %s 没有拿到过 %s" % (role, action))
        del owned[action]
        self._grant_versions[action] = self._grant_versions.get(action, 0) + 1

    def deny(self, role, action):
        """记一条拒绝：角色（及其子角色）不允许这个动作模式。

        显式拒绝压过一切允许，哪怕允许更精确或来自更近的祖先。
        """
        validate_pattern(action)
        self._require(role)
        denied = self._denials[role]
        if action in denied:
            raise DuplicateDeny("角色 %s 已经拒绝过 %s" % (role, action))
        denied[action] = None
        self._deny_versions[action] = self._deny_versions.get(action, 0) + 1

    def granted(self, role):
        """角色直接拿到的动作模式，按授予顺序。"""
        self._require(role)
        return list(self._grants[role])

    def denials(self, role):
        """角色直接拒绝的动作模式，按拒绝顺序。"""
        self._require(role)
        return list(self._denials[role])

    def allowed(self, role, action):
        """精确判断角色自己（不看父角色、不看通配）有没有拿到这个动作。"""
        self._require(role)
        return action in self._grants[role]

    # ---- 继承 ----

    def inherit(self, child, parent):
        """让 child 继承 parent：child 吃到 parent 及其祖先的授予与拒绝。

        多父和菱形都允许；重复声明同一条边是空操作。成环（parent 已经
        能经继承走到 child）当场抛 InheritanceCycle，不留半截边。
        """
        self._require(child)
        self._require(parent)
        if parent in self._parents[child]:
            return
        if child == parent or self._reaches(parent, child):
            raise InheritanceCycle(
                "继承成环: %s -> %s（%s 已经是 %s 的后代）"
                % (child, parent, parent, child))
        self._parents[child][parent] = None
        self._children[parent][child] = None
        self._graph_version += 1

    def _reaches(self, start, target):
        """从 start 沿父边向上能不能走到 target（迭代 DFS，环安全）。"""
        stack = list(self._parents[start])
        seen = set()
        while stack:
            role = stack.pop()
            if role == target:
                return True
            if role in seen:
                continue
            seen.add(role)
            stack.extend(self._parents[role])
        return False

    def parents(self, role):
        """角色直接继承的父角色，按 inherit 先后。"""
        self._require(role)
        return list(self._parents[role])

    def children(self, role):
        """直接继承该角色的子角色，按 inherit 先后。"""
        self._require(role)
        return list(self._children[role])

    # ---- 版本号（Engine 缓存失效用）----

    def graph_version(self):
        return self._graph_version

    def grant_version(self, pattern):
        return self._grant_versions.get(pattern, 0)

    def deny_version(self, pattern):
        return self._deny_versions.get(pattern, 0)

    # ---- 汇总 ----

    def rules(self):
        """全部授予，按先角色声明序、后动作授予序展开成 (role, action)。"""
        out = []
        for role in self._roles:
            for action in self._grants[role]:
                out.append((role, action))
        return out

    def stats(self):
        return {
            "roles": len(self._roles),
            "grants": sum(len(owned) for owned in self._grants.values()),
            "denies": sum(len(owned) for owned in self._denials.values()),
            "inheritances": sum(len(owned)
                                for owned in self._parents.values()),
        }
