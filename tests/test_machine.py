"""fsmguard 语义测试：逐条锁定 README「语义约定」。

以 README 为唯一行为基准。与 README 不符的实际行为用红用例钉出，
红用例上方注释写明「README 期望 / 实际发生」。

可独立重复运行：
    python3 -m unittest tests.test_machine -v
    python3 tests/test_machine.py -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fsmguard import Machine


class GuardBoom(Exception):
    """守卫抛出的自定义异常，用于断言原样传播。"""


class ActionBoom(Exception):
    """entry/exit 动作抛出的自定义异常。"""


class TestFireBasic(unittest.TestCase):
    def setUp(self):
        self.fsm = Machine("idle")
        self.fsm.add_transition("start", "idle", "running")

    def test_accepted_transition_returns_true_and_moves_state(self):
        # README 1：接受并完成一次转移返回 True
        self.assertTrue(self.fsm.fire("start"))
        self.assertEqual(self.fsm.state, "running")

    def test_no_matching_transition_returns_false_and_keeps_state(self):
        # README 1：当前状态没有该事件的转移 -> False，状态不变，不视为错误
        self.assertFalse(self.fsm.fire("nope"))
        self.assertEqual(self.fsm.state, "idle")

    def test_no_matching_transition_records_no_history(self):
        # README 6：无匹配的尝试一律不记录
        self.fsm.fire("nope")
        self.assertEqual(self.fsm.history, [])

    def test_history_records_completed_transition(self):
        # README 6：记录 {"event", "from", "to"}，追加顺序即完成顺序
        self.fsm.add_transition("stop", "running", "idle")
        self.fsm.fire("start")
        self.fsm.fire("stop")
        self.assertEqual(
            self.fsm.history,
            [
                {"event": "start", "from": "idle", "to": "running"},
                {"event": "stop", "from": "running", "to": "idle"},
            ],
        )


class TestTransitionSelection(unittest.TestCase):
    def setUp(self):
        self.fsm = Machine("busy.compile")

    def test_parent_transition_applies_to_child_state(self):
        # README 2：busy.compile 位于 source busy 之下，父转移对子状态生效
        self.fsm.add_transition("stop", "busy", "idle")
        self.assertTrue(self.fsm.fire("stop"))
        self.assertEqual(self.fsm.state, "idle")

    # 红用例（缺陷 1：最具体者未优先）
    # README 期望：busy.compile 与 busy 上都注册了 stop 转移时，
    #   source 路径段数多者（busy.compile，2 段）优先被采用，进入 child-target。
    # 实际发生：_pick 按 depth 升序排序后取第一个，选中了更浅的父转移
    #   （busy，1 段），状态被带到 parent-target。
    def test_child_transition_takes_precedence_over_parent(self):
        self.fsm.add_transition("stop", "busy", "parent-target")
        self.fsm.add_transition("stop", "busy.compile", "child-target")
        self.assertTrue(self.fsm.fire("stop"))
        self.assertEqual(self.fsm.state, "child-target")

    def test_exact_source_match_is_a_candidate(self):
        self.fsm.add_transition("stop", "busy.compile", "idle")
        self.assertTrue(self.fsm.fire("stop"))
        self.assertEqual(self.fsm.state, "idle")

    def test_dotted_prefix_is_not_a_path_match(self):
        # README 2：只有等于 source 或位于 source 之下（source + "."）才算匹配，
        # 名字前缀相同不构成父子关系
        fsm = Machine("busy2")
        fsm.add_transition("stop", "busy", "idle")
        self.assertFalse(fsm.fire("stop"))
        self.assertEqual(fsm.state, "busy2")


class TestFallback(unittest.TestCase):
    def test_fallback_used_when_no_candidate(self):
        # README 3：当前状态没有任何候选转移时使用默认转移
        fsm = Machine("idle")
        fsm.add_fallback("reset", "init")
        self.assertTrue(fsm.fire("reset"))
        self.assertEqual(fsm.state, "init")

    def test_fallback_history_from_is_star(self):
        # README 6：默认转移触发时 from 记为 "*"
        fsm = Machine("idle")
        fsm.add_fallback("reset", "init")
        fsm.fire("reset")
        self.assertEqual(
            fsm.history,
            [{"event": "reset", "from": "*", "to": "init"}],
        )

    # 红用例（缺陷 2：默认转移在存在候选时仍然被采用）
    # README 期望：idle 上存在 start 候选转移时，默认转移不参与选择，
    #   fire("start") 应走到 running。
    # 实际发生：fire 中先取 _fallbacks 再 _pick（`fallback or pick`），
    #   默认转移无条件胜出，状态被带到 fb-target。
    def test_fallback_ignored_when_candidate_exists(self):
        fsm = Machine("idle")
        fsm.add_transition("start", "idle", "running")
        fsm.add_fallback("start", "fb-target")
        self.assertTrue(fsm.fire("start"))
        self.assertEqual(fsm.state, "running")

    # 红用例（缺陷 2 的另一面：守卫拒绝的候选不触发默认转移）
    # README 期望：默认转移仅在「没有任何候选转移」时使用；候选存在但被
    #   守卫拒绝时 fire 返回 False、状态不变。
    # 实际发生：fallback 先于候选被选中，守卫根本不被求值，转移照走，
    #   fire 返回 True、状态变为 fb-target。
    def test_fallback_not_used_when_guard_rejects_candidate(self):
        fsm = Machine("idle")
        fsm.add_transition("start", "idle", "running", guard=lambda m: False)
        fsm.add_fallback("start", "fb-target")
        self.assertFalse(fsm.fire("start"))
        self.assertEqual(fsm.state, "idle")
        self.assertEqual(fsm.history, [])

    def test_can_reflects_candidates_but_not_fallback(self):
        # README：can 只判断当前状态是否存在该事件的候选转移；
        # 仅有默认转移而无候选时不算候选
        fsm = Machine("idle")
        fsm.add_fallback("reset", "init")
        self.assertFalse(fsm.can("reset"))


class TestGuards(unittest.TestCase):
    def setUp(self):
        self.fsm = Machine("idle")

    def test_truthy_guard_allows_transition(self):
        # README 4：返回真值放行
        self.fsm.add_transition("start", "idle", "running", guard=lambda m: True)
        self.assertTrue(self.fsm.fire("start"))
        self.assertEqual(self.fsm.state, "running")

    def test_falsy_guard_rejects_transition(self):
        # README 4：返回假值拒绝，状态不变，fire 返回 False
        self.fsm.add_transition("start", "idle", "running", guard=lambda m: False)
        self.assertFalse(self.fsm.fire("start"))
        self.assertEqual(self.fsm.state, "idle")

    def test_rejected_guard_runs_no_actions_and_no_history(self):
        # README 4 + 6：拒绝时转移不发生，exit 动作不应执行，history 不记录
        exited = []
        self.fsm.on_exit("idle", lambda m: exited.append("exit"))
        self.fsm.add_transition("start", "idle", "running", guard=lambda m: False)
        self.assertFalse(self.fsm.fire("start"))
        self.assertEqual(exited, [])
        self.assertEqual(self.fsm.history, [])

    def test_guard_receives_machine_instance(self):
        # README 4：guard(machine)
        seen = []

        def guard(m):
            seen.append(m)
            return True

        self.fsm.add_transition("start", "idle", "running", guard=guard)
        self.fsm.fire("start")
        self.assertIs(seen[0], self.fsm)

    # 红用例（缺陷 3：守卫异常被吞掉并当作放行）
    # README 期望：guard 抛异常时异常原样向 fire 调用方传播，状态不得变化、
    #   不写 history，既不当放行也不当拒绝。
    # 实际发生：fire 用 try/except 吞掉守卫异常并把 allowed 置为 True，
    #   转移照常完成（fire 不抛、状态变到 running、history 多一条）。
    def test_guard_exception_propagates_and_state_unchanged(self):
        def boom(_m):
            raise GuardBoom("guard failure")

        self.fsm.add_transition("start", "idle", "running", guard=boom)
        with self.assertRaises(GuardBoom):
            self.fsm.fire("start")
        self.assertEqual(self.fsm.state, "idle")
        self.assertEqual(self.fsm.history, [])

    def test_can_ignores_guards(self):
        # README：can 不做守卫判断，守卫为假时候选依然存在
        self.fsm.add_transition("start", "idle", "running", guard=lambda m: False)
        self.assertTrue(self.fsm.can("start"))

    def test_can_true_for_parent_matched_transition(self):
        fsm = Machine("busy.compile")
        fsm.add_transition("stop", "busy", "idle")
        self.assertTrue(fsm.can("stop"))


class TestEntryExitActions(unittest.TestCase):
    def test_exit_then_entry_run_in_order(self):
        # README 5：接受转移后依次执行源状态 exit、目标状态 entry
        order = []
        fsm = Machine("running")
        fsm.add_transition("pause", "running", "paused")
        fsm.on_exit("running", lambda m: order.append("exit-running"))
        fsm.on_enter("paused", lambda m: order.append("enter-paused"))
        fsm.fire("pause")
        self.assertEqual(order, ["exit-running", "enter-paused"])

    def test_exit_action_exception_rolls_back(self):
        # README 5：exit 动作抛异常时异常原样传播，状态保持转移前，不写 history。
        # 此时状态尚未切换，天然满足回滚——钉住这一既有正确行为。
        order = []
        fsm = Machine("running")
        fsm.add_transition("pause", "running", "paused")

        def boom(_m):
            order.append("exit-boom")
            raise ActionBoom("exit failure")

        fsm.on_exit("running", boom)
        fsm.on_enter("paused", lambda m: order.append("enter-paused"))
        with self.assertRaises(ActionBoom):
            fsm.fire("pause")
        self.assertEqual(fsm.state, "running")
        self.assertEqual(fsm.history, [])
        self.assertEqual(order, ["exit-boom"])

    # 红用例（缺陷 4：entry 动作异常后状态不回滚且写入 history）
    # README 期望：entry 动作抛异常时异常向调用方传播，状态必须保持转移前
    #   的 running，且该次转移不得写入 history（要么完整发生，要么不发生）。
    # 实际发生：fire 先切状态、先 append history，最后才跑 entry；异常抛出时
    #   状态已停在 paused、history 已记录，转移处于半完成状态。
    def test_entry_action_exception_rolls_back(self):
        def boom(_m):
            raise ActionBoom("entry failure")

        fsm = Machine("running")
        fsm.add_transition("pause", "running", "paused")
        fsm.on_enter("paused", boom)
        with self.assertRaises(ActionBoom):
            fsm.fire("pause")
        self.assertEqual(fsm.state, "running")
        self.assertEqual(fsm.history, [])


class TestHistory(unittest.TestCase):
    def test_only_completed_transitions_recorded(self):
        # README 6：被拒绝、无匹配、动作异常的尝试一律不记录，
        # 只有实际完成的转移按完成顺序追加
        def boom(_m):
            raise ActionBoom

        fsm = Machine("idle")
        fsm.add_transition("start", "idle", "running")
        fsm.add_transition("deny", "running", "x", guard=lambda m: False)
        fsm.add_transition("boom", "running", "x")
        fsm.on_exit("running", boom)
        fsm.fire("start")
        fsm.fire("nope")
        fsm.fire("deny")
        with self.assertRaises(ActionBoom):
            fsm.fire("boom")
        self.assertEqual(
            fsm.history,
            [{"event": "start", "from": "idle", "to": "running"}],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
