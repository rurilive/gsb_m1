"""任务：状态机、派生、取消与落定回调。"""

from .errors import Cancelled, InvalidTransition, SchedulerError

PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELLED = "cancelled"

STATES = (PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED)
SETTLED_STATES = frozenset((SUCCEEDED, FAILED, CANCELLED))

#: 合法状态转换表。落定之后的三个状态都是终态，不再向外转换。
LEGAL_TRANSITIONS = {
    PENDING: (RUNNING, CANCELLED),
    RUNNING: (SUCCEEDED, FAILED, CANCELLED),
    SUCCEEDED: (),
    FAILED: (),
    CANCELLED: (),
}


def check_transition(current, target):
    """校验一次状态转换，表里没有的组合抛 InvalidTransition。"""
    if target not in LEGAL_TRANSITIONS.get(current, ()):
        raise InvalidTransition(current, target)
    return target


class Task:
    """一个可以派生子任务、设置延迟与超时、能被取消的任务。"""

    def __init__(self, scheduler, task_id, name, body, *, delay=0.0, timeout=None,
                 parent=None):
        self.scheduler = scheduler
        self.id = task_id
        self.name = name
        self.delay = delay
        self.timeout = timeout
        self.parent = parent
        self.children = []
        self.state = PENDING
        self.error = None
        self.history = [PENDING]
        self._body = body
        self._callbacks = []
        self._body_done = False
        self._open_children = 0

    def __repr__(self):
        return "<Task {} #{} {}>".format(self.name, self.id, self.state)

    @property
    def done(self):
        """是否已经落定（成功、失败或取消）。"""
        return self.state in SETTLED_STATES

    @property
    def cancelled(self):
        return self.state is CANCELLED

    # -- 对外动作 --------------------------------------------------------

    def spawn(self, name, body, *, delay=0.0, timeout=None, on_done=None):
        """派生一个子任务，父任务要等它落定之后才会收尾。"""
        if self.state is not RUNNING:
            raise SchedulerError("task {} is not running".format(self.name))
        return self.scheduler._spawn(self, name, body, delay, timeout, on_done)

    def cancel(self, reason="cancelled"):
        """请求取消这个任务派出去的整棵子树。

        已经落定的任务不受影响，返回 False；本次调用把任务落定为取消
        时返回 True。落定回调恰好触发一次。
        """
        self._transition(CANCELLED, Cancelled(reason))
        self.scheduler._forget_task(self.id)
        if self.parent is not None:
            self.scheduler._notify_parent(self.parent, self)
        self._fire_done()
        return True

    def add_done_callback(self, callback):
        """挂一个落定回调；任务已经落定时立即触发一次。"""
        if self.state in SETTLED_STATES:
            callback(self)
            return
        self._callbacks.append(callback)

    # -- 内部推进 --------------------------------------------------------

    def _transition(self, state, error=None):
        """把任务推进到新状态，并记进 history。"""
        self.history.append(state)
        self.state = state
        self.error = error

    def _start(self):
        if self.state is not PENDING:
            return
        self._transition(RUNNING)
        try:
            self._body(self)
        except Exception as exc:
            self._settle(FAILED, exc)
            return
        self._body_done = True
        self._maybe_finish()

    def _maybe_finish(self):
        """任务体跑完且子任务全部落定之后收尾。"""
        if not self._body_done or self._open_children:
            return
        for child in self.children:
            if child.state is not SUCCEEDED:
                return
        self._settle(SUCCEEDED)

    def _child_settled(self, child):
        """某个子任务落定了，减掉一个待收的孩子。"""
        self._open_children -= 1
        self._maybe_finish()

    def _settle(self, state, error=None):
        """落定：写状态、撤销定时器、通知父任务、触发回调。"""
        self._transition(state, error)
        self.scheduler._drop_timer(self.id, "start")
        self.scheduler._drop_timer(self.id, "deadline")
        if self.parent is not None:
            self.scheduler._notify_parent(self.parent, self)
        self._fire_done()

    def _fire_done(self):
        for callback in list(self._callbacks):
            callback(self)
