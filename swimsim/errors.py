"""swimsim 自有异常类型。

成员协议的构造期与运行期可诊断错误都在这里定义，全部继承 SwimError，
调用方只捕捉 SwimError 即可一次性接住所有协议错误。
"""


class SwimError(Exception):
    """swimsim 所有可诊断错误的基类。"""


class DefinitionError(SwimError):
    """定义期错误：成员名非法、同名成员重复加入等。"""


class UnknownMember(SwimError):
    """未知成员：查状态的成员不在成员表里。"""


class IllegalTransition(SwimError):
    """非法状态转移：目标状态不被当前状态所允许。"""


class SelfProbeRejected(SwimError):
    """自探测：探测的目标等于发起探测的节点自己。"""


class NotHeartbeatTime(SwimError):
    """推进时机未到：还没到下一个心跳周期。"""