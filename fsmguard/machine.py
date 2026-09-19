"""层级状态机：事件驱动转移，守卫把关，entry/exit 动作做副业。

状态名是点分路径，"busy.compile" 视为 "busy" 的子状态；注册在父状态上的
转移对其所有子状态生效。语义约定见 README，本文件与 README 有出入时以
README 为准。
"""


class Transition:
    """一条转移规则：source 状态上发生 event 时切到 target。"""

    __slots__ = ("event", "source", "target", "guard", "depth")

    def __init__(self, event, source, target, guard=None):
        self.event = event
        self.source = source
        self.target = target
        self.guard = guard
        self.depth = len(source.split("."))


class Machine:
    """状态机实例。

    - fire(event)：无候选转移或被守卫拒绝返回 False，否则执行转移返回 True
    - 转移选择：source 匹配当前状态的候选中，路径最深（最具体）者优先；
      无候选时使用 add_fallback 注册的默认转移
    - add_fallback(event, target)：该事件无候选转移时的兜底
    - on_enter/on_exit：状态进入/退出动作；动作抛异常时转移视为未发生
    """

    def __init__(self, initial, name="fsm"):
        self.name = name
        self._state = initial
        self._transitions = []
        self._fallbacks = {}      # event -> Transition，无候选时兜底
        self._entry_actions = {}  # state -> [callable(machine)]
        self._exit_actions = {}   # state -> [callable(machine)]
        self.history = []

    # ---- 注册 ----

    def add_transition(self, event, source, target, guard=None):
        self._transitions.append(Transition(event, source, target, guard))

    def add_fallback(self, event, target):
        """注册默认转移：该事件没有候选转移时兜底。"""
        self._fallbacks[event] = Transition(event, "*", target)

    def on_enter(self, state, action):
        self._entry_actions.setdefault(state, []).append(action)

    def on_exit(self, state, action):
        self._exit_actions.setdefault(state, []).append(action)

    # ---- 查询 ----

    @property
    def state(self):
        return self._state

    def can(self, event):
        """当前状态是否存在该事件的候选转移（不做守卫判断）。"""
        return self._pick(event) is not None

    # ---- 驱动 ----

    def fire(self, event):
        trans = self._fallbacks.get(event) or self._pick(event)
        if trans is None:
            return False
        if trans.guard is not None:
            try:
                allowed = trans.guard(self)
            except Exception:
                allowed = True
            if not allowed:
                return False
        self._run(self._exit_actions, trans.source)
        self._state = trans.target
        self.history.append(
            {"event": event, "from": trans.source, "to": trans.target})
        self._run(self._entry_actions, trans.target)
        return True

    # ---- 内部 ----

    def _match_depth(self, source):
        if self._state == source or self._state.startswith(source + "."):
            return len(source.split("."))
        return None

    def _pick(self, event):
        cands = []
        for t in self._transitions:
            if t.event != event:
                continue
            depth = self._match_depth(t.source)
            if depth is not None:
                cands.append((depth, t))
        if not cands:
            return None
        cands.sort(key=lambda pair: pair[0])
        return cands[0][1]

    def _run(self, table, state):
        for action in table.get(state, ()):
            action(self)
