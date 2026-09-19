"""fsmguard 语义测试：以 fsmguard/README.md 的「语义约定」为唯一基准。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests -v

每个用例独立构造 Machine，可单独、可重复运行。
"""

import unittest

from fsmguard import Machine


class Boom(Exception):
    """测试专用的守卫/动作异常。"""


def raise_boom(_machine):
    raise Boom("boom")


class TestFireBasic(unittest.TestCase):
    """README 约定 1：fire(event) -> bool。"""

    def test_accepted_transition_returns_true_and_changes_state(self):
        m = Machine("idle")
        m.add_transition("start", "idle", "running")
        self.assertTrue(m.fire("start"))
        self.assertEqual(m.state, "running")

    def test_no_matching_event_returns_false_state_unchanged(self):
        m = Machine("idle")
        m.add_transition("start", "idle", "running")
        self.assertFalse(m.fire("stop"))
        self.assertEqual(m.state, "idle")

    def test_wrong_source_returns_false_state_unchanged(self):
        m = Machine("paused")
        m.add_transition("start", "idle", "running")
        self.assertFalse(m.fire("start"))
        self.assertEqual(m.state, "paused")


class TestTransitionSelection(unittest.TestCase):
    """README 约定 2：候选匹配与最具体者优先。"""

    def test_parent_transition_applies_to_child_state(self):
        m = Machine("busy.compile")
        m.add_transition("abort", "busy", "idle")
        self.assertTrue(m.fire("abort"))
        self.assertEqual(m.state, "idle")

    def test_sibling_state_does_not_match(self):
        m = Machine("busy.link")
        m.add_transition("done", "busy.compile", "idle")
        self.assertFalse(m.fire("done"))
        self.assertEqual(m.state, "busy.link")

    def test_most_specific_transition_wins(self):
        # README 期望：父/子状态同事件并存时，source 路径段数多者优先，
        #   即 busy.compile 上的转移先于 busy 上的转移被采用，
        #   fire("abort") 后状态应为 "busy.review"。
        # 实际发生：源码按路径段数升序排序后取第一条，最宽泛者优先，
        #   实际转到 "idle"。
        m = Machine("busy.compile")
        m.add_transition("abort", "busy", "idle")
        m.add_transition("abort", "busy.compile", "busy.review")
        m.fire("abort")
        self.assertEqual(m.state, "busy.review")


class TestFallback(unittest.TestCase):
    """README 约定 3：默认转移仅在没有候选时使用。"""

    def test_fallback_used_when_no_candidate(self):
        m = Machine("idle")
        m.add_fallback("reset", "idle")
        self.assertTrue(m.fire("reset"))
        self.assertEqual(m.state, "idle")

    def test_fallback_history_from_is_star(self):
        m = Machine("idle")
        m.add_fallback("reset", "idle")
        m.fire("reset")
        self.assertEqual(m.history,
                         [{"event": "reset", "from": "*", "to": "idle"}])

    def test_fallback_ignored_when_candidate_exists(self):
        # README 期望：存在候选转移时默认转移不参与选择，
        #   fire("tick") 应走候选转移到 "b"。
        # 实际发生：源码 `self._fallbacks.get(event) or self._pick(event)`
        #   让默认转移永远抢在候选前面，实际转到 "fallback-target"。
        m = Machine("a")
        m.add_transition("tick", "a", "b")
        m.add_fallback("tick", "fallback-target")
        m.fire("tick")
        self.assertEqual(m.state, "b")


class TestGuard(unittest.TestCase):
    """README 约定 4：守卫放行/拒绝/异常传播。"""

    def test_guard_truthy_allows(self):
        m = Machine("idle")
        m.add_transition("go", "idle", "running", guard=lambda _m: True)
        self.assertTrue(m.fire("go"))
        self.assertEqual(m.state, "running")

    def test_guard_falsy_rejects(self):
        m = Machine("idle")
        m.add_transition("go", "idle", "running", guard=lambda _m: False)
        self.assertFalse(m.fire("go"))
        self.assertEqual(m.state, "idle")
        self.assertEqual(m.history, [])

    def test_guard_receives_machine(self):
        seen = []
        m = Machine("idle")
        m.add_transition("go", "idle", "running",
                         guard=lambda mach: seen.append(mach) or True)
        m.fire("go")
        self.assertEqual(seen, [m])

    def test_guard_exception_propagates_and_state_unchanged(self):
        # README 期望：guard 抛出的异常原样向 fire 调用方传播，
        #   状态不得变化，且不允许把守卫异常当作放行或拒绝处理。
        # 实际发生：源码 try/except 吞掉异常并按「放行」处理，
        #   fire 不抛异常，状态被切到 "running"，history 也被写入。
        m = Machine("idle")
        m.add_transition("go", "idle", "running", guard=raise_boom)
        with self.assertRaises(Boom):
            m.fire("go")
        self.assertEqual(m.state, "idle")
        self.assertEqual(m.history, [])


class TestActionsAtomicity(unittest.TestCase):
    """README 约定 5：entry/exit 动作顺序与转移原子性。"""

    def test_exit_runs_before_entry(self):
        calls = []
        m = Machine("idle")
        m.add_transition("go", "idle", "running")
        m.on_exit("idle", lambda _m: calls.append("exit-idle"))
        m.on_enter("running", lambda _m: calls.append("enter-running"))
        m.fire("go")
        self.assertEqual(calls, ["exit-idle", "enter-running"])

    def test_multiple_actions_run_in_registration_order(self):
        calls = []
        m = Machine("idle")
        m.add_transition("go", "idle", "running")
        m.on_enter("running", lambda _m: calls.append(1))
        m.on_enter("running", lambda _m: calls.append(2))
        m.fire("go")
        self.assertEqual(calls, [1, 2])

    def test_exit_action_exception_rolls_back(self):
        m = Machine("idle")
        m.add_transition("go", "idle", "running")
        m.on_exit("idle", raise_boom)
        with self.assertRaises(Boom):
            m.fire("go")
        self.assertEqual(m.state, "idle")
        self.assertEqual(m.history, [])

    def test_entry_action_exception_rolls_back(self):
        # README 期望：entry 动作抛异常时异常原样传播，且状态必须保持
        #   转移前的状态、该次转移不得写入 history（转移要么完整发生，
        #   要么不发生）。
        # 实际发生：异常确实传播，但源码在 entry 动作之前就已修改状态并
        #   写入 history，异常后状态停留在 "running"、history 多了一条
        #   并未真正完成的转移。
        m = Machine("idle")
        m.add_transition("go", "idle", "running")
        m.on_enter("running", raise_boom)
        with self.assertRaises(Boom):
            m.fire("go")
        self.assertEqual(m.state, "idle")
        self.assertEqual(m.history, [])


class TestHistory(unittest.TestCase):
    """README 约定 6：history 只记录实际完成的转移。"""

    def test_history_records_completed_transitions_in_order(self):
        m = Machine("idle")
        m.add_transition("start", "idle", "running")
        m.add_transition("finish", "running", "done")
        m.fire("start")
        m.fire("finish")
        self.assertEqual(m.history, [
            {"event": "start", "from": "idle", "to": "running"},
            {"event": "finish", "from": "running", "to": "done"},
        ])

    def test_rejected_and_unmatched_attempts_not_recorded(self):
        m = Machine("idle")
        m.add_transition("go", "idle", "running", guard=lambda _m: False)
        m.fire("go")        # 被守卫拒绝
        m.fire("nope")      # 无匹配事件
        self.assertEqual(m.history, [])


class TestCan(unittest.TestCase):
    """README：can(event) 只判断是否存在候选转移，不做守卫判断。"""

    def test_can_true_when_candidate_exists(self):
        m = Machine("busy.compile")
        m.add_transition("abort", "busy", "idle")
        self.assertTrue(m.can("abort"))

    def test_can_false_when_no_candidate(self):
        m = Machine("idle")
        m.add_transition("go", "idle", "running")
        self.assertFalse(m.can("stop"))

    def test_can_ignores_guard(self):
        m = Machine("idle")
        m.add_transition("go", "idle", "running", guard=lambda _m: False)
        self.assertTrue(m.can("go"))


if __name__ == "__main__":
    unittest.main()
