"""多分支分叉与合并的行为测试。

所有时钟都注入确定性的计数器：分支上 append 的 ts 与合并时落线记录的
version/ts 都可精确断言。
"""

import unittest

from changelogd.changelog import (
    DELETE,
    Candidate,
    ChangeLog,
    MergeReport,
)


class CountingClock:
    """从 start 开始，每次调用加 step，返回当前整数时刻。"""

    def __init__(self, start=0, step=1):
        self._now = start
        self._step = step

    def __call__(self):
        self._now += self._step
        return self._now


def diverged_doc(base_version=1):
    """标准分叉：老张改标题+状态+删字段，小李改状态+加标签+续改删字段。"""
    main = ChangeLog(clock=CountingClock(start=0))
    main.append("doc", "title", "草稿", 1)
    main.append("doc", "status", "draft", 1)
    main.append("doc", "wip", "待定", 1)

    zhang = main.fork(base_version, "zhang")
    zhang.append("doc", "title", "老张定稿", 2)
    zhang.append("doc", "status", "review", 2)
    zhang.append("doc", "wip", DELETE, 2)

    li = main.fork(base_version, "li")
    li.append("doc", "status", "done", 2)
    li.append("doc", "tag", "hot", 2)
    li.append("doc", "wip", "小李续改", 2)
    return main, zhang, li


class TestFork(unittest.TestCase):
    def test_fork_keeps_only_base_history(self):
        main = ChangeLog(clock=CountingClock(start=0))
        main.append("doc", "title", "草稿", 1)
        main.append("doc", "status", "draft", 1)
        main.append("doc", "wip", "待定", 1)
        main.append("doc", "title", "主线后续", 2)
        zhang = main.fork(1, "zhang")
        self.assertEqual(
            [(c.field, c.value) for c in zhang.history("doc")],
            [("title", "草稿"), ("status", "draft"), ("wip", "待定")],
        )
        self.assertEqual(
            zhang.at("doc", 1),
            {"title": "草稿", "status": "draft", "wip": "待定"})
        # fork 只复制已有记录、不调用时钟，ts 保持分叉时原值
        self.assertEqual([c.ts for c in zhang.history("doc")], [1, 2, 3])
        # 分叉之后的提交两边互不串线
        self.assertEqual(
            main.at("doc", 2)["title"], "主线后续")
        zhang.append("doc", "title", "老张定稿", 2)
        self.assertEqual(zhang.at("doc", 2)["title"], "老张定稿")
        self.assertEqual(main.at("doc", 2)["title"], "主线后续")

    def test_fork_independent_append(self):
        main, zhang, _ = diverged_doc()
        zhang.append("doc", "title", "再改", 3)
        self.assertEqual([c.field for c in zhang.history("doc")][-1], "title")
        self.assertEqual(len(main.history("doc")), 3)


class TestMerge(unittest.TestCase):
    def test_default_merge_folds_snapshot(self):
        main, zhang, li = diverged_doc()
        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)], clock=CountingClock(100))
        # 状态冲突按列出顺序取老张；删除压过小李对 wip 的修改；
        # 标题、标签各归各并进来。
        self.assertEqual(
            main.at("doc", report.version),
            {"title": "老张定稿", "status": "review", "tag": "hot"})
        self.assertIsInstance(report, MergeReport)

    def test_merge_versions_come_from_merge_clock(self):
        main, zhang, li = diverged_doc()
        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)], clock=CountingClock(100))
        # 落线记录：status、wip 冲突各 2 条 + title/tag 各 1 条 = 6 条，
        # version 与 ts 都取自合并时钟，逐条递增。
        ticks = [(e.change.version, e.change.ts) for e in report.merged]
        self.assertEqual(ticks, [(n, n) for n in range(101, 107)])
        self.assertEqual(report.version, 106)

    def test_every_merged_entry_is_traced_to_branch(self):
        main, zhang, li = diverged_doc()
        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)], clock=CountingClock(100))
        by_field = {}
        for entry in report.merged:
            by_field.setdefault(entry.change.field, []).append(entry)
        self.assertEqual(
            [(e.branch, e.state) for e in by_field["title"]],
            [("zhang", "winner")])
        self.assertEqual(
            [(e.branch, e.state) for e in by_field["tag"]],
            [("li", "winner")])
        self.assertEqual(
            [(e.branch, e.state) for e in by_field["status"]],
            [("li", "loser"), ("zhang", "winner")])

    def test_provenance_aligns_with_history(self):
        main, zhang, li = diverged_doc()
        main.merge_branches(
            1, [("zhang", zhang), ("li", li)], clock=CountingClock(100))
        history = main.history("doc")
        provenance = main.provenance("doc")
        self.assertEqual(len(history), len(provenance))
        # 分叉前的三条没有来源，之后每条都有分支名
        self.assertEqual(provenance[:3], [None, None, None])
        self.assertEqual(set(provenance[3:]), {"zhang", "li"})
        for change, branch in zip(history[3:], provenance[3:]):
            self.assertIn(branch, ("zhang", "li"))
            self.assertIsNotNone(change.ts)

    def test_losers_are_listed_for_audit(self):
        main, zhang, li = diverged_doc()
        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)], clock=CountingClock(100))
        losers = report.losers()
        self.assertEqual(
            [(e.change.field, e.branch, e.change.value) for e in losers],
            [("status", "li", "done"), ("wip", "li", "小李续改")])
        fields = {conflict.field: conflict for conflict in report.conflicts}
        self.assertEqual(set(fields), {"status", "wip"})
        self.assertEqual(fields["status"].winner, "zhang")
        self.assertEqual(fields["status"].losers, ["li"])
        self.assertIsInstance(fields["status"].candidates[0], Candidate)
        self.assertEqual(fields["wip"].winner, "zhang")  # 删除方赢

    def test_deleted_then_modified_leaves_trace_but_no_snapshot(self):
        main, zhang, li = diverged_doc()
        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)], clock=CountingClock(100))
        wip_after = [
            c for c in main.history("doc")
            if c.field == "wip" and c.version > 1]
        # 历史里老张的删除和小李的修改都看得见
        self.assertEqual(len(wip_after), 2)
        self.assertIn(DELETE, [c.value for c in wip_after])
        self.assertIn("小李续改", [c.value for c in wip_after])
        # 最终快照里 wip 不再冒出
        self.assertNotIn("wip", main.at("doc", report.version))

    def test_delete_alone_removes_field_from_snapshot(self):
        main = ChangeLog(clock=CountingClock())
        main.append("doc", "tag", "x", 1)
        branch = main.fork(1, "b")
        branch.append("doc", "tag", DELETE, 2)
        report = main.merge_branches(
            1, [("b", branch)], clock=CountingClock(100))
        self.assertNotIn("tag", main.at("doc", report.version))
        self.assertEqual(
            [(c.field, c.value) for c in main.history("doc")][-1],
            ("tag", DELETE))


class TestResolvers(unittest.TestCase):
    def test_latest_wins_prefers_later_branch_order(self):
        main, zhang, li = diverged_doc()
        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)],
            resolver="latest-wins", clock=CountingClock(100))
        self.assertEqual(main.at("doc", report.version)["status"], "done")
        self.assertEqual(
            [(e.change.field, e.branch) for e in report.losers()],
            [("status", "zhang"), ("wip", "zhang")])

    def test_first_wins_keeps_list_order(self):
        main, zhang, li = diverged_doc()
        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)],
            resolver="first-wins", clock=CountingClock(100))
        snapshot = main.at("doc", report.version)
        self.assertEqual(snapshot["status"], "review")
        self.assertNotIn("wip", snapshot)  # 老张在前且删了 wip

    def test_latest_ts_wins_uses_change_timestamp(self):
        main = ChangeLog(clock=CountingClock())
        main.append("doc", "status", "draft", 1)
        early = main.fork(1, "early")
        late = main.fork(1, "late")
        early.append("doc", "status", "early-review", 2)
        late.append("doc", "status", "late-done", 2)
        report = main.merge_branches(
            1, [("early", early), ("late", late)],
            resolver="latest-ts-wins", clock=CountingClock(100))
        self.assertEqual(main.at("doc", report.version)["status"], "late-done")

    def test_custom_resolver_signature_and_return(self):
        main, zhang, li = diverged_doc()
        seen = []

        def li_biased(field, candidates, base_version):
            seen.append((field, [c.branch for c in candidates], base_version))
            # 业务口径：小李全赢，返回中选的 Candidate
            return candidates[-1]

        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)],
            resolver=li_biased, clock=CountingClock(100))
        snapshot = main.at("doc", report.version)
        self.assertEqual(snapshot["status"], "done")
        # 自定义消解下 wip 也按业务口径保留小李的值
        self.assertEqual(snapshot["wip"], "小李续改")
        self.assertEqual({field for field, _, _ in seen}, {"status", "wip"})
        for _, branches, base in seen:
            self.assertEqual(branches, ["zhang", "li"])
            self.assertEqual(base, 1)

    def test_custom_resolver_may_return_branch_name(self):
        main, zhang, li = diverged_doc()
        report = main.merge_branches(
            1, [("zhang", zhang), ("li", li)],
            resolver=lambda field, candidates, base: "li",
            clock=CountingClock(100))
        self.assertEqual(main.at("doc", report.version)["status"], "done")
        self.assertEqual(report.conflicts[0].winner, "li")

    def test_unknown_preset_raises(self):
        main, zhang, li = diverged_doc()
        with self.assertRaises(ValueError):
            main.merge_branches(
                1, [("zhang", zhang), ("li", li)], resolver="nope")


class TestMergeSemantics(unittest.TestCase):
    def test_same_value_both_branches_is_no_conflict(self):
        main = ChangeLog(clock=CountingClock())
        main.append("doc", "a", 1, 1)
        b1 = main.fork(1, "b1")
        b2 = main.fork(1, "b2")
        b1.append("doc", "a", 9, 2)
        b2.append("doc", "a", 9, 2)
        report = main.merge_branches(
            1, [("b1", b1), ("b2", b2)], clock=CountingClock(100))
        self.assertEqual(report.conflicts, [])
        self.assertEqual(len(report.merged), 1)  # 同值只落一份
        self.assertEqual(report.merged[0].branch, "b1")

    def test_distinct_fields_merge_side_by_side(self):
        main = ChangeLog(clock=CountingClock())
        main.append("doc", "a", 1, 1)
        b1 = main.fork(1, "b1")
        b2 = main.fork(1, "b2")
        b1.append("doc", "x", "from-b1", 2)
        b2.append("doc", "y", "from-b2", 2)
        report = main.merge_branches(
            1, [("b1", b1), ("b2", b2)], clock=CountingClock(100))
        self.assertEqual(main.at("doc", report.version),
                         {"a": 1, "x": "from-b1", "y": "from-b2"})

    def test_merge_covers_objects_from_either_branch(self):
        main = ChangeLog(clock=CountingClock())
        main.append("doc1", "a", 1, 1)
        b1 = main.fork(1, "b1")
        b2 = main.fork(1, "b2")
        b1.append("doc2", "a", 2, 2)
        b2.append("doc3", "a", 3, 2)
        report = main.merge_branches(
            1, [("b1", b1), ("b2", b2)], clock=CountingClock(100))
        self.assertEqual(main.at("doc2", report.version), {"a": 2})
        self.assertEqual(main.at("doc3", report.version), {"a": 3})


if __name__ == "__main__":
    unittest.main()
