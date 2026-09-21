"""继承、通配、显式拒绝与 explain 的行为基线。

关键一类测试用“朴素递归展开 + BFS 最短距离”当参考实现，在随机 DAG
（含多父与菱形）、随机授予/拒绝（含通配）上跟 Engine 对拍；环和取舍
规则用固定用例锁死。
"""

import random
import sys
import time
import unittest
from collections import deque

from rbacflow import (
    DuplicateDeny,
    Engine,
    InheritanceCycle,
    InvalidAction,
    PolicyError,
    PolicyStore,
    UnknownRole,
)
from rbacflow.actions import candidates

sys.setrecursionlimit(20000)


# ---- 朴素参考实现：跟 Engine 不共用任何判定代码 ----

_SEGMENT_START = "abcdefghijklmnopqrstuvwxyz"


def naive_validate(action):
    parts = action.split(":")
    for part in parts:
        if not part or part[0] not in _SEGMENT_START:
            raise InvalidAction(action)
        for char in part:
            if not (char.islower() or char.isdigit()):
                raise InvalidAction(action)


def naive_distances(store, role):
    """从 role 沿父边 BFS，给出每个可达角色（含自己）的最短距离。"""
    distances = {role: 0}
    queue = deque([role])
    while queue:
        current = queue.popleft()
        for parent in store._parents[current]:
            if parent not in distances:
                distances[parent] = distances[current] + 1
                queue.append(parent)
    return distances


def naive_decide(store, role, action):
    """返回 (kind, pattern, source, distance)；deny 整体优先。"""
    store._require(role)
    naive_validate(action)
    distances = naive_distances(store, role)

    def best(table):
        # candidates 顺序就是具体程度：精确、长前缀、短前缀、*
        for pattern in candidates(action):
            winner = None
            for owner, distance in distances.items():
                if pattern in table[owner] and (
                        winner is None or distance < winner[1]):
                    winner = (owner, distance)
            if winner is not None:
                return pattern, winner[0], winner[1]
        return None

    denied = best(store._denials)
    if denied is not None:
        return ("deny",) + denied
    granted = best(store._grants)
    if granted is not None:
        return ("allow",) + granted
    return ("default", None, None, None)


class InheritanceCase(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()
        for role in ("base", "mid1", "mid2", "child"):
            self.store.declare(role)
        self.store.grant("base", "pkg:list")
        self.store.grant("mid1", "docs:read")
        self.store.grant("mid2", "docs:write")
        self.store.inherit("mid1", "base")
        self.store.inherit("mid2", "base")
        self.store.inherit("child", "mid1")
        self.store.inherit("child", "mid2")
        self.engine = Engine(self.store)


class TestInheritance(InheritanceCase):

    def test_child_eats_parents_grants(self):
        self.assertTrue(self.engine.check("child", "docs:read"))
        self.assertTrue(self.engine.check("child", "docs:write"))

    def test_grandchild_eats_ancestor_grants(self):
        self.assertTrue(self.engine.check("child", "pkg:list"))
        self.assertTrue(self.engine.check("mid1", "pkg:list"))

    def test_parent_does_not_eat_child(self):
        self.assertFalse(self.engine.check("base", "docs:read"))
        self.assertFalse(self.engine.check("mid1", "docs:write"))

    def test_diamond_grant_visible_once(self):
        self.assertTrue(self.engine.check("child", "pkg:list"))
        explanation = self.engine.explain("child", "pkg:list")
        self.assertEqual(explanation.source, "base")
        self.assertEqual(explanation.distance, 2)
        self.assertEqual(explanation.path[0], "child")
        self.assertEqual(explanation.path[-1], "base")

    def test_parents_and_children_edges(self):
        self.assertEqual(self.store.parents("child"), ["mid1", "mid2"])
        self.assertEqual(self.store.children("base"), ["mid1", "mid2"])
        self.assertEqual(self.store.parents("base"), [])

    def test_inherit_unknown_roles(self):
        with self.assertRaises(UnknownRole):
            self.store.inherit("child", "ghost")
        with self.assertRaises(UnknownRole):
            self.store.inherit("ghost", "base")

    def test_duplicate_inherit_is_noop(self):
        before = self.store.stats()["inheritances"]
        self.store.inherit("child", "mid1")
        self.assertEqual(self.store.stats()["inheritances"], before)


class TestCycle(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()
        for role in ("a", "b", "c"):
            self.store.declare(role)

    def test_self_inheritance_is_cycle(self):
        with self.assertRaises(InheritanceCycle):
            self.store.inherit("a", "a")

    def test_direct_back_edge_is_cycle(self):
        self.store.inherit("a", "b")
        with self.assertRaises(InheritanceCycle):
            self.store.inherit("b", "a")

    def test_transitive_cycle_raises_at_declaration(self):
        self.store.inherit("a", "b")
        self.store.inherit("b", "c")
        with self.assertRaises(InheritanceCycle):
            self.store.inherit("c", "a")

    def test_failed_cycle_leaves_no_edge(self):
        self.store.inherit("a", "b")
        self.store.inherit("b", "c")
        with self.assertRaises(InheritanceCycle):
            self.store.inherit("c", "a")
        self.assertEqual(self.store.parents("c"), [])
        self.assertEqual(self.store.children("a"), [])
        self.assertEqual(self.store.stats()["inheritances"], 2)

    def test_cycle_is_policy_error(self):
        with self.assertRaises(PolicyError):
            self.store.inherit("a", "a")

    def test_diamond_is_not_a_cycle(self):
        self.store.declare("top")
        self.store.inherit("a", "top")
        self.store.inherit("b", "top")
        self.store.declare("bottom")
        self.store.inherit("bottom", "a")
        self.store.inherit("bottom", "b")
        self.assertEqual(len(self.store.parents("bottom")), 2)


class TestWildcard(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()
        for role in ("ops", "dev"):
            self.store.declare(role)
        self.engine = Engine(self.store)

    def test_prefix_wildcard_covers_descendants_only(self):
        self.store.grant("ops", "pkg:*")
        self.assertTrue(self.engine.check("ops", "pkg:read"))
        self.assertTrue(self.engine.check("ops", "pkg:sub:list"))
        self.assertFalse(self.engine.check("ops", "pkg"))
        self.assertFalse(self.engine.check("ops", "pkgx:read"))

    def test_bare_star_covers_everything(self):
        self.store.grant("ops", "*")
        self.assertTrue(self.engine.check("ops", "docs:read"))
        self.assertTrue(self.engine.check("ops", "pkg:sub:list"))
        self.assertTrue(self.engine.check("ops", "anything"))

    def test_wildcard_inheritance(self):
        self.store.grant("ops", "pkg:*")
        self.store.inherit("dev", "ops")
        self.assertTrue(self.engine.check("dev", "pkg:deploy"))
        self.assertFalse(self.engine.check("dev", "docs:read"))

    def test_invalid_wildcard_patterns(self):
        for bad in ("", ":*", "*:read", "pkg:*:list", "pkg::*",
                    "pkg:*:", "Pkg:*", "pkg:Read"):
            with self.assertRaises(InvalidAction):
                self.store.grant("ops", bad)
            with self.assertRaises(InvalidAction):
                self.store.deny("ops", bad)

    def test_check_rejects_wildcard_as_action(self):
        self.store.grant("ops", "pkg:*")
        with self.assertRaises(InvalidAction):
            self.engine.check("ops", "pkg:*")


class TestDeny(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()
        for role in ("base", "child"):
            self.store.declare(role)
        self.store.inherit("child", "base")
        self.engine = Engine(self.store)

    def test_deny_blocks_direct_grant(self):
        self.store.grant("child", "docs:read")
        self.assertTrue(self.engine.check("child", "docs:read"))
        self.store.deny("child", "docs:read")
        self.assertFalse(self.engine.check("child", "docs:read"))

    def test_ancestor_deny_beats_descendant_allow(self):
        self.store.grant("child", "pkg:delete")
        self.store.deny("base", "pkg:delete")
        self.assertFalse(self.engine.check("child", "pkg:delete"))

    def test_ancestor_deny_beats_descendant_wildcard_allow(self):
        self.store.grant("child", "pkg:*")
        self.store.deny("base", "pkg:delete")
        self.assertFalse(self.engine.check("child", "pkg:delete"))
        self.assertTrue(self.engine.check("child", "pkg:read"))

    def test_deny_wildcard_beats_exact_allow(self):
        self.store.grant("child", "docs:read")
        self.store.deny("child", "docs:*")
        self.assertFalse(self.engine.check("child", "docs:read"))

    def test_duplicate_deny_rejected(self):
        self.store.deny("base", "docs:*")
        with self.assertRaises(DuplicateDeny):
            self.store.deny("base", "docs:*")

    def test_deny_unknown_role(self):
        with self.assertRaises(UnknownRole):
            self.store.deny("ghost", "docs:read")

    def test_denials_listed_in_order(self):
        self.store.deny("base", "docs:*")
        self.store.deny("base", "pkg:delete")
        self.assertEqual(self.store.denials("base"),
                         ["docs:*", "pkg:delete"])


class TestSpecificity(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()

    def test_exact_beats_wildcard(self):
        self.store.declare("r")
        self.store.grant("r", "pkg:*")
        self.store.deny("r", "pkg:read")
        explanation = Engine(self.store).explain("r", "pkg:read")
        self.assertFalse(explanation.allowed)
        self.assertEqual(explanation.pattern, "pkg:read")
        self.assertEqual(explanation.match, "exact")

    def test_longer_prefix_beats_shorter_on_allow(self):
        for role in ("a", "b"):
            self.store.declare(role)
        self.store.grant("a", "pkg:*")
        self.store.grant("b", "pkg:sub:*")
        self.store.inherit("b", "a")
        explanation = Engine(self.store).explain("b", "pkg:sub:list")
        self.assertTrue(explanation.allowed)
        self.assertEqual(explanation.pattern, "pkg:sub:*")
        self.assertEqual(explanation.source, "b")

    def test_nearer_beats_farther_same_pattern(self):
        for role in ("top", "mid", "bot"):
            self.store.declare(role)
        self.store.grant("top", "pkg:*")
        self.store.grant("mid", "pkg:*")
        self.store.inherit("mid", "top")
        self.store.inherit("bot", "mid")
        explanation = Engine(self.store).explain("bot", "pkg:read")
        self.assertTrue(explanation.allowed)
        self.assertEqual(explanation.source, "mid")
        self.assertEqual(explanation.distance, 1)
        self.assertEqual(explanation.path, ("bot", "mid"))

    def test_exact_far_beats_wildcard_near(self):
        # 精确压通配，哪怕精确的来自更远的祖先
        for role in ("top", "bot"):
            self.store.declare(role)
        self.store.grant("top", "docs:read")
        self.store.grant("bot", "docs:*")
        self.store.inherit("bot", "top")
        explanation = Engine(self.store).explain("bot", "docs:read")
        self.assertEqual(explanation.pattern, "docs:read")
        self.assertEqual(explanation.source, "top")
        self.assertEqual(explanation.match, "exact")

    def test_deny_always_outranks_allow(self):
        # 允许更精确、更近，拒绝更宽、更远：照样拒绝
        for role in ("far", "near"):
            self.store.declare(role)
        self.store.grant("near", "pkg:read")
        self.store.deny("far", "pkg:*")
        self.store.inherit("near", "far")
        explanation = Engine(self.store).explain("near", "pkg:read")
        self.assertFalse(explanation.allowed)
        self.assertEqual(explanation.kind, "deny")
        self.assertEqual(explanation.pattern, "pkg:*")
        self.assertEqual(explanation.source, "far")

    def test_most_specific_deny_is_reported(self):
        # 多条 deny 都命中时，报最具体的那条
        for role in ("a", "b"):
            self.store.declare(role)
        self.store.deny("a", "pkg:*")
        self.store.deny("b", "pkg:sub:*")
        self.store.inherit("b", "a")
        explanation = Engine(self.store).explain("b", "pkg:sub:list")
        self.assertEqual(explanation.pattern, "pkg:sub:*")
        self.assertEqual(explanation.source, "b")


class TestExplain(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()
        for role in ("base", "mid", "child"):
            self.store.declare(role)
        self.store.inherit("mid", "base")
        self.store.inherit("child", "mid")
        self.engine = Engine(self.store)

    def test_explain_allow_direct(self):
        self.store.grant("child", "docs:read")
        explanation = self.engine.explain("child", "docs:read")
        self.assertTrue(explanation.allowed)
        self.assertEqual(explanation.kind, "allow")
        self.assertEqual(explanation.pattern, "docs:read")
        self.assertEqual(explanation.source, "child")
        self.assertEqual(explanation.distance, 0)
        self.assertEqual(explanation.path, ("child",))
        self.assertEqual(explanation.match, "exact")
        self.assertTrue(bool(explanation))
        self.assertIn("docs:read", explanation.reason)

    def test_explain_allow_inherited_names_chain(self):
        self.store.grant("base", "pkg:*")
        explanation = self.engine.explain("child", "pkg:read")
        self.assertTrue(explanation.allowed)
        self.assertEqual(explanation.source, "base")
        self.assertEqual(explanation.distance, 2)
        self.assertEqual(explanation.path, ("child", "mid", "base"))
        self.assertEqual(explanation.match, "wildcard")

    def test_explain_deny_names_rule_source_and_chain(self):
        self.store.grant("child", "pkg:delete")
        self.store.deny("base", "pkg:delete")
        explanation = self.engine.explain("child", "pkg:delete")
        self.assertFalse(explanation.allowed)
        self.assertEqual(explanation.kind, "deny")
        self.assertEqual(explanation.pattern, "pkg:delete")
        self.assertEqual(explanation.source, "base")
        self.assertEqual(explanation.distance, 2)
        self.assertEqual(explanation.path, ("child", "mid", "base"))
        self.assertFalse(bool(explanation))
        reason = explanation.reason
        self.assertIn("deny", reason)
        self.assertIn("base", reason)
        self.assertIn("pkg:delete", reason)

    def test_explain_default_deny(self):
        explanation = self.engine.explain("child", "nothing:here")
        self.assertFalse(explanation.allowed)
        self.assertEqual(explanation.kind, "default")
        self.assertIsNone(explanation.pattern)
        self.assertIsNone(explanation.source)
        self.assertIsNone(explanation.path)

    def test_explain_as_dict_and_indexing(self):
        self.store.grant("child", "docs:read")
        explanation = self.engine.explain("child", "docs:read")
        data = explanation.as_dict()
        self.assertEqual(data["allowed"], True)
        self.assertEqual(data["kind"], "allow")
        self.assertEqual(explanation["source"], "child")
        self.assertEqual(set(data.keys()),
                         {"allowed", "kind", "pattern", "source",
                          "distance", "path", "match", "reason"})

    def test_explain_unknown_role_and_invalid_action(self):
        with self.assertRaises(UnknownRole):
            self.engine.explain("ghost", "docs:read")
        with self.assertRaises(InvalidAction):
            self.engine.explain("child", "docs:Read")


class TestLiveUpdates(unittest.TestCase):

    def setUp(self):
        self.store = PolicyStore()
        for role in ("base", "child"):
            self.store.declare(role)
        self.store.inherit("child", "base")
        self.engine = Engine(self.store)

    def test_grant_visible_after_warm_miss(self):
        self.assertFalse(self.engine.check("child", "docs:read"))
        self.assertEqual(
            self.engine.explain("child", "docs:read").kind, "default")
        self.store.grant("base", "docs:read")
        self.assertTrue(self.engine.check("child", "docs:read"))
        explanation = self.engine.explain("child", "docs:read")
        self.assertEqual(explanation.source, "base")

    def test_revoke_takes_effect_through_cache(self):
        self.store.grant("base", "docs:read")
        self.assertTrue(self.engine.check("child", "docs:read"))
        self.store.revoke("base", "docs:read")
        self.assertFalse(self.engine.check("child", "docs:read"))

    def test_deny_takes_effect_through_cache(self):
        self.store.grant("base", "docs:read")
        self.assertTrue(self.engine.check("child", "docs:read"))
        self.store.deny("base", "docs:read")
        self.assertFalse(self.engine.check("child", "docs:read"))

    def test_new_inheritance_edge_takes_effect(self):
        self.store.declare("newbie")
        self.store.grant("base", "secret:open")
        self.assertFalse(self.engine.check("newbie", "secret:open"))
        self.store.inherit("newbie", "base")
        self.assertTrue(self.engine.check("newbie", "secret:open"))

    def test_unrelated_grant_does_not_disturb_other_patterns(self):
        self.store.grant("base", "pkg:*")
        self.assertTrue(self.engine.check("child", "pkg:read"))
        # 给另一个模式加规则，pkg:* 的结论和依据不应被冲掉
        self.store.grant("base", "docs:read")
        explanation = self.engine.explain("child", "pkg:read")
        self.assertEqual(explanation.pattern, "pkg:*")
        self.assertEqual(explanation.source, "base")


class TestRandomDagFuzz(unittest.TestCase):
    """随机 DAG + 随机规则，跟朴素参考实现逐条对拍。"""

    ACTION_POOL = (
        "docs:read", "docs:write", "docs:delete",
        "pkg:list", "pkg:read", "pkg:write", "pkg:delete",
        "pkg:sub:list", "pkg:sub:write",
        "secret:open", "audit:export",
    )
    PATTERN_POOL = ACTION_POOL + ("*", "docs:*", "pkg:*", "pkg:sub:*")

    def _build(self, rng, size):
        store = PolicyStore()
        roles = ["r%04d" % i for i in range(size)]
        for role in roles:
            store.declare(role)
        # 边只能从小编号指向大编号，天然无环；允许 0~3 个父，制造菱形
        for i in range(2, size):
            parents = rng.sample(range(i), min(i, rng.randrange(0, 4)))
            for parent in parents:
                store.inherit(roles[i], roles[parent])
        for role in roles:
            if rng.random() < 0.25:
                for pattern in rng.sample(
                        self.PATTERN_POOL, rng.randrange(1, 4)):
                    if pattern not in store._grants[role]:
                        store.grant(role, pattern)
            if rng.random() < 0.12:
                pattern = rng.choice(self.PATTERN_POOL)
                if pattern not in store._denials[role]:
                    store.deny(role, pattern)
        return store, roles

    def _assert_match(self, engine, store, role, action):
        expected = naive_decide(store, role, action)
        explanation = engine.explain(role, action)
        kind, pattern, source, distance = expected
        self.assertEqual(explanation.kind, kind,
                         msg="%s %s: kind %s != %s"
                             % (role, action, explanation.kind, kind))
        self.assertEqual(bool(explanation.allowed), kind == "allow")
        if kind != "default":
            self.assertEqual(explanation.pattern, pattern)
            self.assertEqual(explanation.source, source)
            self.assertEqual(explanation.distance, distance)
            if distance:
                self.assertEqual(explanation.path[0], role)
                self.assertEqual(explanation.path[-1], source)
                self.assertEqual(len(explanation.path), distance + 1)

    def test_random_graphs_and_queries(self):
        rng = random.Random(20260921)
        for round_index in range(24):
            size = rng.randrange(8, 45)
            store, roles = self._build(rng, size)
            engine = Engine(store)
            for _ in range(120):
                role = rng.choice(roles)
                action = rng.choice(self.ACTION_POOL)
                self._assert_match(engine, store, role, action)

    def test_random_mutations_keep_engine_consistent(self):
        rng = random.Random(424242)
        store, roles = self._build(rng, 30)
        engine = Engine(store)
        for _ in range(300):
            choice = rng.random()
            role = rng.choice(roles)
            if choice < 0.35:
                pattern = rng.choice(self.PATTERN_POOL)
                if pattern not in store._grants[role]:
                    store.grant(role, pattern)
            elif choice < 0.55:
                pattern = rng.choice(self.PATTERN_POOL)
                if pattern not in store._denials[role]:
                    store.deny(role, pattern)
            elif choice < 0.75:
                held = store.granted(role)
                if held:
                    store.revoke(role, rng.choice(held))
            else:
                # 尽量指向前方角色；即便如此也可能因已有路径成环，
                # 成环的边按语义必须当场被拒，跳过即可
                index = int(role[1:])
                if index + 1 < len(roles):
                    parent = roles[rng.randrange(index + 1, len(roles))]
                    try:
                        store.inherit(role, parent)
                    except InheritanceCycle:
                        pass
            action = rng.choice(self.ACTION_POOL)
            self._assert_match(engine, store, role, action)


class TestScale(unittest.TestCase):

    def test_deep_chain_over_recursion_limit(self):
        # 1200 级单链：朴素递归会炸栈，Engine 必须照常判定
        depth = 1200
        store = PolicyStore()
        for i in range(depth):
            store.declare("n%d" % i)
        for i in range(1, depth):
            store.inherit("n%d" % i, "n%d" % (i - 1))
        store.grant("n0", "pkg:*")
        store.deny("n%d" % (depth // 2), "pkg:locked")
        engine = Engine(store)

        leaf = "n%d" % (depth - 1)
        self.assertTrue(engine.check(leaf, "pkg:read"))
        explanation = engine.explain(leaf, "pkg:read")
        self.assertEqual(explanation.source, "n0")
        self.assertEqual(explanation.distance, depth - 1)
        self.assertEqual(len(explanation.path), depth)

        locked = engine.explain(leaf, "pkg:locked")
        self.assertEqual(locked.kind, "deny")
        self.assertEqual(locked.source, "n%d" % (depth // 2))
        self.assertEqual(locked.distance, depth - 1 - depth // 2)

        # 环检测在深链上也应当场抛出而不是递归炸栈
        with self.assertRaises(InheritanceCycle):
            store.inherit("n0", leaf)

    def test_large_store_throughput(self):
        # 五万角色、十万规则：百万次判定要在十秒预算内（热查询走记忆）
        roles_count = 50000
        grants_count = 100000
        store = PolicyStore()
        for i in range(roles_count):
            store.declare("r%d" % i)
        # 一条上千级的深链，其余角色挂到链上随机位置
        chain = 1200
        for i in range(1, chain):
            store.inherit("r%d" % i, "r%d" % (i - 1))
        rng = random.Random(7)
        for i in range(chain, roles_count):
            store.inherit("r%d" % i, "r%d" % rng.randrange(0, chain))
        patterns = ("pkg:read", "pkg:write", "pkg:delete", "pkg:sub:list",
                    "docs:read", "docs:write", "*", "pkg:*", "docs:*",
                    "pkg:sub:*")
        placed = 0
        while placed < grants_count:
            role = "r%d" % rng.randrange(roles_count)
            pattern = patterns[rng.randrange(len(patterns))]
            if pattern not in store._grants[role]:
                store.grant(role, pattern)
                placed += 1
        store.deny("r%d" % (chain // 2), "pkg:delete")

        engine = Engine(store)
        query_roles = ["r%d" % i
                       for i in (0, chain - 1, roles_count - 1,
                                 roles_count // 2, chain, chain + 1)]
        actions = ("pkg:read", "pkg:write", "pkg:delete", "pkg:sub:list",
                   "docs:read", "docs:write")

        checks = 0
        start = time.perf_counter()
        while checks < 1000000:
            for role in query_roles:
                for action in actions:
                    engine.check(role, action)
                    checks += 1
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 10.0,
                        msg="百万判定用时 %.2fs" % elapsed)

        # 中途加规则，下一次判定立即生效，不用重建引擎
        store.grant("r0", "brand:new")
        self.assertTrue(
            engine.check("r%d" % (roles_count - 1), "brand:new"))


if __name__ == "__main__":
    unittest.main()
