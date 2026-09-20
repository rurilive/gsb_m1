"""转移表：状态机行为的唯一来源。

表按 (当前状态, 事件) 组织，同一组合可以有多行（用守卫区分）；
Session 按书写顺序取第一条全部守卫通过的行执行，没有任何行生效
视为协议违规，抛 ProtocolError。

Row 字段：
- next    目标状态；提供 resolve 时可省略（None）
- guards  守卫元组，签名 (payload, session) -> bool
- actions 动作元组，签名 (session, payload)，状态变更后按序执行
- sends   发出的对端消息名元组，进 outbox 并写日志
- timer   进入目标状态后武装的定时器秒数；None 表示该状态无定时器
- resolve 动态目标解析器 (payload, session) -> State；提供时覆盖 next，
          供“返回进入前状态”这类运行时才知道的目标使用
"""

from collections import namedtuple

from .states import (
    SUITES,
    Ev,
    State,
    T_AUTH,
    T_HELLO,
    T_KEY,
    REKEY_TIMEOUT,
)

Row = namedtuple(
    "Row", "state event next guards actions sends timer resolve",
    defaults=(None, (), (), (), None, None),
)


def suite_known(payload, session):
    """守卫：对端报的套件是已知的。"""
    return payload in SUITES


def suite_is_strong(payload, session):
    return session.suite == "strong"


def suite_is_weak(payload, session):
    return session.suite == "weak"


def store_suite(session, payload):
    """动作：记下本会话协商出的套件。"""
    session.suite = payload


def remember_return(target):
    """动作工厂：记下子流程返回的目标稳态（进入前所在稳态）。"""
    def action(session, payload):
        session.rekey_return = target
    return action


def restore_return(payload, session):
    """动态目标：回进入子流程前的稳态。"""
    return session.rekey_return


TABLE = [
    # 握手推进
    Row(State.CLOSED, Ev.START, State.HELLO_SENT, sends=("c_hello",),
        timer=T_HELLO),
    Row(State.HELLO_SENT, Ev.PEER_HELLO, State.KEY_SENT,
        guards=(suite_known,), actions=(store_suite,), sends=("c_key",),
        timer=T_KEY),
    Row(State.KEY_SENT, Ev.PEER_KEY, State.AUTH_SENT, sends=("c_auth",),
        timer=T_AUTH),
    # 认证结果按套件分流到两个稳态
    Row(State.AUTH_SENT, Ev.PEER_AUTH_OK, State.FULL,
        guards=(suite_is_strong,)),
    Row(State.AUTH_SENT, Ev.PEER_AUTH_OK, State.DEGRADED,
        guards=(suite_is_weak,)),
    Row(State.AUTH_SENT, Ev.PEER_AUTH_FAIL, State.CLOSED,
        sends=("c_close",)),
    # 各阶段超时：整体放弃，回 CLOSED
    Row(State.HELLO_SENT, Ev.TIMEOUT, State.CLOSED),
    Row(State.KEY_SENT, Ev.TIMEOUT, State.CLOSED),
    Row(State.AUTH_SENT, Ev.TIMEOUT, State.CLOSED),
    # 稳态下对端要求关闭
    Row(State.FULL, Ev.PEER_CLOSE, State.CLOSED, sends=("c_close",)),
    Row(State.DEGRADED, Ev.PEER_CLOSE, State.CLOSED, sends=("c_close",)),

    # rekey 子流程：任一稳态都可触发，三步协商新密钥
    # 发 rekey-offer -> 收 accept 发 rekey-confirm -> 收 done 提交并回原稳态；
    # 成功与超时都走 resolve 回进入前的稳态，连接不断
    Row(State.FULL, Ev.REKEY, State.REKEY_OFFER_SENT,
        actions=(remember_return(State.FULL),), sends=("rekey-offer",),
        timer=REKEY_TIMEOUT),
    Row(State.DEGRADED, Ev.REKEY, State.REKEY_OFFER_SENT,
        actions=(remember_return(State.DEGRADED),), sends=("rekey-offer",),
        timer=REKEY_TIMEOUT),
    Row(State.REKEY_OFFER_SENT, Ev.PEER_REKEY_ACCEPT,
        State.REKEY_CONFIRM_SENT, sends=("rekey-confirm",),
        timer=REKEY_TIMEOUT),
    Row(State.REKEY_CONFIRM_SENT, Ev.PEER_REKEY_DONE, None,
        sends=("rekey-done-ack",), resolve=restore_return),
    # 每步超时：弃用新密钥，回进入前的稳态（连接保持）
    Row(State.REKEY_OFFER_SENT, Ev.TIMEOUT, None,
        resolve=restore_return),
    Row(State.REKEY_CONFIRM_SENT, Ev.TIMEOUT, None,
        resolve=restore_return),
]
