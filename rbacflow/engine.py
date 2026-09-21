"""策略判定入口。"""

from .actions import validate


class Engine(object):
    """对着一个 PolicyStore 做判定。

    当前口径：角色能做某动作，当且仅当它自己直接拿到过这个名字的动作。
    store 里改了授权，下一次判定马上看得到。
    """

    def __init__(self, store):
        self.store = store

    def check(self, role, action):
        """角色能不能做这个动作。

        角色没声明抛 UnknownRole，动作名不合法抛 InvalidAction。
        """
        validate(action)
        return self.store.allowed(role, action)

    def check_many(self, role, actions):
        """一次判一批动作，返回动作到布尔值的字典，保持传入顺序。"""
        return {action: self.check(role, action) for action in actions}

    def permitted(self, role):
        """角色直接拿到的全部动作，按授予顺序。"""
        return self.store.granted(role)
