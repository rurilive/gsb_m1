"""分叉合并行为测试：冲突消解、删除坑、来源与输家记账。

全部时钟注入，版本与 ts 都可断言。
"""

import unittest

from changelogd.changelog import ChangeLog
from changelogd.merge import DELETE, first_wins, merge


def make_log(clock, changes):
    """changes: [(field, value, version), ...]，全部记到 doc-1。"""
    log = ChangeLog(clock=clock)
    for field, value, version in changes:
        log.append("doc-1", field, value, version)
    return log


def diverged_branches():
    """老张、小李从 v2 分叉。

    老张 v3：改标题、改状态为 shipped、删截止日；
    小李 v3：改状态为 review、补标签、又把已删的截止日改成新日期。
    """
    zhang = make_log(iter([10.0, 11.0, 12.0]).__next__, [
        ("title", "老张定稿", 3),
        ("status", "shipped", 3),
        ("due", DELETE, 3),
    ])
    li = make_log(iter([20.0, 21.0, 22.0]).__next__, [
        ("status", "review", 3),
        ("tag", "hotfix", 3),
        ("due", "2026-10-01", 3),
    ])
    return zhang, li


def merge_default(zhang, li, **kwargs):
    ticks = iter([100.0, 101.0, 102.0, 103.0])
    return merge(
        "doc-1", 2, [("zhang", zhang), ("li", li)],
        clock=ticks.__next__, **kwargs
    )


class TestMergeBasics(unittest.TestCase):
    def test_disjoint_fields_merge_in_side_by_side(self):
        result = merge(
            "doc-1", 1,
            [("zhang", make_log(iter([1.0]).__next__, [("title", "t", 2)])),
             ("li", make_log(iter([2.0]).__next__, [("tag", "x", 2)]))],
            clock=iter([100.0, 200.0]).__next__,
        )
        self.assertEqual(result.snapshot(), {"title": "t", "tag": "x"})
        self.assertEqual([e.field for e in result.entries()], ["title", "tag"])
        self.assertEqual(result.source_of("title"), ("zhang",))
        self.assertEqual(result.source_of("tag"), ("li",))
        self.assertEqual(result.conflicts(), [])

    def test_default_conflict_takes_first_branch(self):
        zhang, li = diverged_branches()
        result = merge_default(zhang, li)
        status = next(e for e in result.entries() if e.field == "status")
        self.assertEqual(status.value, "shipped")
        self.assertEqual(status.sources, ("zhang",))
        self.assertEqual(result.source_of("status"), ("zhang",))

    def test_merge_superimposes_on_base_snapshot(self):
        base = make_log(iter([0.0, 0.1]).__next__, [
            ("title", "旧标题", 1),
            ("due", "2026-09-30", 2),
        ])
        zhang = make_log(iter([10.0]).__next__, [("title", "老张定稿", 3)])
        li = make_log(iter([20.0]).__next__, [("tag", "hotfix", 3)])
        result = merge(
            "doc-1", 2, [("zhang", zhang), ("li", li)],
            base=base,
            clock=iter([100.0, 101.0]).__next__,
        )
        self.assertEqual(
            result.snapshot(),
            {"title": "老张定稿", "due": "2026-09-30", "tag": "hotfix"},
        )

    def test_version_defaults_to_base_plus_one_and_is_injectable(self):
        zhang = make_log(iter([1.0]).__next__, [("a", 1, 7)])
        li = make_log(iter([2.0]).__next__, [("b", 2, 7)])
        result = merge("doc-1", 7, [("zhang", zhang), ("li", li)],
                       clock=iter([9.0, 9.1]).__next__)
        self.assertTrue(all(e.version == 8 for e in result.entries()))
        result2 = merge("doc-1", 7, [("zhang", zhang), ("li", li)],
                        version=42, clock=iter([9.0, 9.1]).__next__)
        self.assertTrue(all(e.version == 42 for e in result2.entries()))

    def test_clock_called_once_per_merged_field(self):
        zhang, li = diverged_branches()
        result = merge_default(zhang, li)
        by_field = {e.field: e for e in result.entries()}
        self.assertEqual(
            {field: entry.ts for field, entry in by_field.items()},
            {"title": 100.0, "status": 101.0, "due": 102.0, "tag": 103.0},
        )


class TestDeletion(unittest.TestCase):
    def test_delete_then_modified_field_is_absent_from_snapshot(self):
        base = make_log(iter([0.0]).__next__, [("due", "2026-09-30", 2)])
        zhang, li = diverged_branches()
        result = merge_default(zhang, li, base=base)
        self.assertNotIn("due", result.snapshot())
        self.assertEqual(result.source_of("due"), ())

    def test_delete_remains_visible_in_merged_history(self):
        zhang, li = diverged_branches()
        result = merge_default(zhang, li)
        due = next(e for e in result.history() if e.field == "due")
        self.assertIs(due.value, DELETE)
        self.assertEqual(due.sources, ("zhang",))
        # 小李后改的 due 作为输家留在账里，中间发生过什么看得见
        conflict = next(c for c in result.conflicts() if c.field == "due")
        self.assertEqual(conflict.winner, "zhang")
        self.assertEqual(len(conflict.losers), 1)
        self.assertEqual(conflict.losers[0].branch, "li")
        self.assertEqual(conflict.losers[0].value, "2026-10-01")
        self.assertEqual(conflict.losers[0].change.version, 3)

    def test_delete_wins_even_under_latest_ts_strategy(self):
        zhang, li = diverged_branches()  # 删除 ts=12，小李修改 ts=22
        result = merge_default(zhang, li, resolver="latest-ts")
        self.assertNotIn("due", result.snapshot())
        due = next(e for e in result.entries() if e.field == "due")
        self.assertIs(due.value, DELETE)
        self.assertEqual(result.source_of("due"), ())


class TestResolvers(unittest.TestCase):
    def test_latest_ts_strategy_picks_later_change(self):
        zhang, li = diverged_branches()  # 状态 ts 11 vs 20
        result = merge_default(zhang, li, resolver="latest-ts")
        status = next(e for e in result.entries() if e.field == "status")
        self.assertEqual(status.value, "review")
        self.assertEqual(status.sources, ("li",))

    def test_custom_resolver_with_business_rule(self):
        # 业务口径：status 冲突一律以 review 为准；其它字段走默认约定
        def resolve(candidates, base_value):
            if candidates[0].change.field == "status":
                for candidate in candidates:
                    if candidate.value == "review":
                        return candidate
            return first_wins(candidates, base_value)

        zhang, li = diverged_branches()
        result = merge_default(zhang, li, resolver=resolve)
        self.assertEqual(result.snapshot().get("status"), "review")
        self.assertEqual(result.source_of("status"), ("li",))
        # 同一次合并里 due 仍走默认删除口径
        self.assertNotIn("due", result.snapshot())

    def test_custom_resolver_may_return_branch_name(self):
        zhang, li = diverged_branches()
        result = merge_default(
            zhang, li, resolver=lambda candidates, base: "li"
        )
        # 返回 "li" 对 due 也选小李：自定义口径不再保证删除赢
        status = next(e for e in result.entries() if e.field == "status")
        self.assertEqual(status.value, "review")
        due = next(e for e in result.entries() if e.field == "due")
        self.assertEqual(due.value, "2026-10-01")

    def test_custom_resolver_may_return_index(self):
        zhang, li = diverged_branches()
        result = merge_default(
            zhang, li, resolver=lambda candidates, base: 0
        )
        self.assertEqual(result.snapshot().get("status"), "shipped")

    def test_unknown_strategy_raises(self):
        zhang, li = diverged_branches()
        with self.assertRaises(ValueError):
            merge_default(zhang, li, resolver="roll-the-dice")


class TestProvenanceAndLosers(unittest.TestCase):
    def test_every_entry_carries_branch_source(self):
        zhang, li = diverged_branches()
        result = merge_default(zhang, li)
        sources = {e.field: e.sources for e in result.entries()}
        self.assertEqual(sources["title"], ("zhang",))
        self.assertEqual(sources["status"], ("zhang",))
        self.assertEqual(sources["due"], ("zhang",))
        self.assertEqual(sources["tag"], ("li",))

    def test_identical_changes_credit_both_branches(self):
        zhang = make_log(iter([1.0]).__next__, [("status", "review", 3)])
        li = make_log(iter([2.0]).__next__, [("status", "review", 3)])
        result = merge(
            "doc-1", 2, [("zhang", zhang), ("li", li)],
            clock=iter([100.0]).__next__,
        )
        entry = result.entries()[0]
        self.assertEqual(entry.value, "review")
        self.assertEqual(entry.sources, ("zhang", "li"))
        self.assertEqual(result.source_of("status"), ("zhang", "li"))
        self.assertEqual(result.conflicts(), [])
        self.assertEqual(result.losers(), [])

    def test_losers_list_all_resolved_candidates(self):
        a = make_log(iter([1.0]).__next__, [("status", "open", 3)])
        b = make_log(iter([2.0]).__next__, [("status", "review", 3)])
        c = make_log(iter([3.0]).__next__, [("status", "shipped", 3)])
        ticks = iter([100.0])
        result = merge(
            "doc-1", 2, [("a", a), ("b", b), ("c", c)],
            clock=ticks.__next__,
        )
        self.assertEqual(result.snapshot()["status"], "open")
        losers = result.losers()
        self.assertEqual(
            [(candidate.branch, candidate.value) for candidate in losers],
            [("b", "review"), ("c", "shipped")],
        )
        conflict = result.conflicts()[0]
        self.assertEqual(conflict.winner, "a")
        self.assertIs(conflict.resolver, first_wins)
        self.assertEqual(conflict.version, 3)
        self.assertEqual(conflict.ts, 100.0)

    def test_originals_keep_full_branch_records_for_audit(self):
        zhang, li = diverged_branches()
        result = merge_default(zhang, li)
        status = next(e for e in result.entries() if e.field == "status")
        self.assertEqual(len(status.originals), 2)
        self.assertEqual(
            [(candidate.branch, candidate.change.ts)
             for candidate in status.originals],
            [("zhang", 11.0), ("li", 20.0)],
        )


class TestMergeValidationAndCommit(unittest.TestCase):
    def test_duplicate_branch_names_rejected(self):
        a = make_log(iter([1.0]).__next__, [("x", 1, 2)])
        b = make_log(iter([2.0]).__next__, [("y", 2, 2)])
        with self.assertRaises(ValueError):
            merge("doc-1", 1, [("same", a), ("same", b)])

    def test_single_branch_is_not_a_merge(self):
        a = make_log(iter([1.0]).__next__, [("x", 1, 2)])
        with self.assertRaises(ValueError):
            merge("doc-1", 1, [("lonely", a)])

    def test_commit_replays_merge_onto_single_timeline(self):
        base = make_log((lambda: 0.0), [("due", "2026-09-30", 2)])
        zhang, li = diverged_branches()
        result = merge_default(zhang, li, base=base)
        result.commit(base, version=4)
        # 合并结果原样追加（DELETE 作为删除记录），历史全程留痕
        self.assertEqual(
            [c.field for c in base.history("doc-1")],
            ["due", "title", "status", "due", "tag"],
        )
        due_records = [c for c in base.history("doc-1") if c.field == "due"]
        self.assertEqual(due_records[-1].value, DELETE)
        merged_fields = [c for c in base.history("doc-1")][-4:]
        self.assertTrue(all(c.version == 4 for c in merged_fields))
        # 删除口径由合并快照负责，不改动单线 at 的基线行为
        self.assertEqual(
            result.snapshot(base.at("doc-1", 2)),
            {"title": "老张定稿", "status": "shipped", "tag": "hotfix"},
        )


if __name__ == "__main__":
    unittest.main()
