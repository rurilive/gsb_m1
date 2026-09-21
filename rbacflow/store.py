"""角色与授权的本地存放。

PolicyStore 是策略库的全部状态：哪些角色存在，每个角色直接拿到了哪些动作。
判定本身不在这里，Engine 把它当唯一事实来源。
"""

from .actions import validate
from .errors import DuplicateGrant, NotGranted, PolicyError, UnknownRole


class PolicyStore(object):
    """角色到动作的授予表。

    一个角色可以拿到多个动作，一个动作也可以同时被多个角色拿到；角色按声明
    的先后排列，同一角色的动作按授予的先后排列。
    """

    def __init__(self):
        self._roles = []       # 角色名，声明序
        self._grants = {}      # 角色名 -> {动作: None}，授予序

    # ---- 角色 ----

    def declare(self, role):
        """声明一个角色；重复声明是空操作。"""
        if not isinstance(role, str) or not role:
            raise PolicyError("角色名必须是非空字符串: %r" % (role,))
        if role not in self._grants:
            self._roles.append(role)
            self._grants[role] = {}

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
        """给角色直接授予一个动作。"""
        validate(action)
        self._require(role)
        owned = self._grants[role]
        if action in owned:
            raise DuplicateGrant("角色 %s 已经拿到过 %s" % (role, action))
        owned[action] = None

    def revoke(self, role, action):
        """撤掉角色直接拿到的某个动作。"""
        self._require(role)
        owned = self._grants[role]
        if action not in owned:
            raise NotGranted("角色 %s 没有拿到过 %s" % (role, action))
        del owned[action]

    def granted(self, role):
        """角色直接拿到的动作，按授予顺序。"""
        self._require(role)
        return list(self._grants[role])

    def allowed(self, role, action):
        """精确判断角色自己（不看别的角色）有没有拿到这个动作。"""
        self._require(role)
        return action in self._grants[role]

    # ---- 汇总 ----

    def rules(self):
        """全部授予，按先角色声明序、后动作授予序展开成 (role, action)。"""
        out = []
        for role in self._roles:
            for action in self._grants[role]:
                out.append((role, action))
        return out

    def stats(self):
        return {"roles": len(self._roles),
                "grants": sum(len(owned) for owned in self._grants.values())}
