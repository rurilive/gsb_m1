"""转移表：状态机行为的唯一来源。

表按 (当前状态, 事件) 组织，同一组合可以有多行（用守卫区分）；
Session 按书写顺序取第一条全部守卫通过的行执行，没有任何行生效
视为协议违规，抛 ProtocolError。

Row 字段：
- next    目标状态
- next_fn 动态目标，签名 (payload, session) -> State；优先于 next，
          用于“回进入前稳态”这类运行时才定的目标
- guards  守卫元组，签名 (payload, session) -> bool
- actions 动作元组，签名 (session, payload)，状态变更后按序执行
- sends   发出的对端消息名元组，进 outbox 并写日志
- timer   进入目标状态后武装的定时器秒数；None 表示该状态无定时器
"""

from collections import namedtuple

from .states import (
    SUITES,
    Ev,
    REKEY_TIMEOUT,
    State,
    T_AUTH,
    T_HELLO,
    T_KEY,
)

Row = namedtuple(
    "Row", "state event next next_fn guards actions sends timer",
    defaults=(None, (), (), (), None),
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


def remember_rekey_resume_from_full(session, payload):
    """动作：rekey 前记住来源稳态 FULL。"""
    session.rekey_resume = State.FULL


def remember_rekey_resume_from_degraded(session, payload):
    """动作：rekey 前记住来源稳态 DEGRADED。"""
    session.rekey_resume = State.DEGRADED


def resume_steady(payload, session):
    """动态目标：回进入 rekey 子流程前的稳态。"""
    return session.rekey_resume


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
    # rekey 子流程：任一稳态可触发，三步 offer/accept/confirm/done，
    # 每步各武装 REKEY_TIMEOUT；成功或超时都回进入前记的稳态
    Row(State.FULL, Ev.REKEY, State.REKEY_OFFER_SENT,
        actions=(remember_rekey_resume_from_full,),
        sends=("rekey-offer",), timer=REKEY_TIMEOUT),
    Row(State.DEGRADED, Ev.REKEY, State.REKEY_OFFER_SENT,
        actions=(remember_rekey_resume_from_degraded,),
        sends=("rekey-offer",), timer=REKEY_TIMEOUT),
    Row(State.REKEY_OFFER_SENT, Ev.PEER_REKEY_ACCEPT,
        State.REKEY_CONFIRM_SENT,
        sends=("rekey-confirm",), timer=REKEY_TIMEOUT),
    Row(State.REKEY_CONFIRM_SENT, Ev.PEER_REKEY_DONE,
        None, next_fn=resume_steady),
    Row(State.REKEY_OFFER_SENT, Ev.TIMEOUT, None, next_fn=resume_steady),
    Row(State.REKEY_CONFIRM_SENT, Ev.TIMEOUT, None, next_fn=resume_steady),
]
