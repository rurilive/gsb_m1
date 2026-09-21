"""rbacflow 的错误类型。"""


class PolicyError(Exception):
    """策略库相关错误的基类。"""


class UnknownRole(PolicyError):
    """引用了一个没有声明过的角色。"""


class InvalidAction(PolicyError):
    """动作名不符合命名规范。"""


class DuplicateGrant(PolicyError):
    """同一个角色对同一个动作重复授予。"""


class NotGranted(PolicyError):
    """撤销一条没有授予过的授权。"""


class DuplicateDeny(PolicyError):
    """同一个角色对同一个动作模式重复拒绝。"""


class InheritanceCycle(PolicyError):
    """继承关系串成了环：子角色已经是父角色的祖先。"""
