"""多分支合并行为测试：注入时钟断言版本号与来源标注。"""

import unittest

from changelogd.changelog import ChangeLog
from changelogd.merge import (
    DELETE,
    Candidate,
    fork,
    last_write_wins,
    merge,
    prefer_branch,
)


def _clock(values):
    ticks = iter(values)
    return lambda: next(ticks)


def _diverged_doc():
    """老张和小李从 v1 分叉的标准场景。

    基准 v1：title=草稿、status=draft。
    老张（ts 20/15）：title=老张标题、status=done。
    小李（ts 11/25）：status=review、tag=hot。
    合并时钟：ts 100 起，每次 append 走一格。
    """
    base = ChangeLog(clock=lambda: 0.0)
    base.append("doc", "title", "草稿", 1)
    base.append("doc", "status", "draft", 1)

    zhang = fork(base, "zhang", clock=_clock([20.0, 15.0]))
    zhang.log.append("doc", "title", "老张标题", 2)
    zhang.log.append("doc", "status", "done", 2)

    li = fork(base, "li", clock=_clock([11.0, 25.0]))
    li.log.append("doc", "status", "review", 2)
    li.log.append("doc", "tag", "hot", 2)

    result = merge(
        "doc", base, [zhang, li], 1, clock=_clock([100.0, 101.0, 102.0])
    )
    return base, zhang, li, result


class TestMergeFields(unittest.TestCase):
    def test_distinct_fields_both_land(self):
        _, _, _, result = _diverged_doc()
        snapshot = result.at("doc")
        self.assertEqual(snapshot["title"], "老张标题")
        self.assertEqual(snapshot["tag"], "hot")

    def test_merged_version_continues_after_base(self):
        _, _, _, result = _diverged_doc()
        entries = result.history("doc")
        # 基准两条 v1 原样保留，并入的三条依次拿 v2、v3、v4。
        self.assertEqual(
            [(m.version, m.field) for m in entries],
            [(1, "title"), (1, "status"), (2, "status"),
             (3, "title"), (4, "tag")],
        )
        self.assertEqual(
            [m.ts for m in entries], [0.0, 0.0, 100.0, 101.0, 102.0]
        )

    def test_merged_order_follows_branch_change_time(self):
        # 赢家按其分支改动时刻排队：status(15)、title(20)、tag(25)。
        _, _, _, result = _diverged_doc()
        fields = [m.field for m in result.history("doc") if m.version > 1]
        self.assertEqual(fields, ["status", "title", "tag"])


class TestProvenance(unittest.TestCase):
    def test_each_merged_entry_names_its_branch(self):
        _, _, _, result = _diverged_doc()
        by_field = {
            m.field: m.sources for m in result.history("doc") if m.version > 1
        }
        self.assertEqual(by_field["title"], ["zhang"])
        self.assertEqual(by_field["status"], ["zhang"])
        self.assertEqual(by_field["tag"], ["li"])

    def test_base_entries_have_no_branch_origin(self):
        _, _, _, result = _diverged_doc()
        base_entries = [m for m in result.history("doc") if m.version == 1]
        self.assertEqual([m.sources for m in base_entries], [[], []])
        for change in result.log().history("doc")[:2]:
            self.assertEqual(result.origin(change), [])

    def test_origin_lookup_takes_a_change_record(self):
        _, _, _, result = _diverged_doc()
        winner = next(c for c in result.log().history("doc") if c.field == "tag")
        self.assertEqual(result.origin(winner), ["li"])

    def test_agreed_change_is_attributed_to_both_branches(self):
        base = ChangeLog(clock=lambda: 0.0)
        base.append("doc", "title", "草稿", 1)
        zhang = fork(base, "zhang", clock=_clock([10.0]))
        zhang.log.append("doc", "title", "同一个", 2)
        li = fork(base, "li", clock=_clock([20.0]))
        li.log.append("doc", "title", "同一个", 2)
        result = merge("doc", base, [zhang, li], 1, clock=_clock([100.0]))
        merged = [m for m in result.history("doc") if m.version > 1]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].sources, ["li", "zhang"])
        self.assertEqual(result.conflicts("doc"), [])


class TestConflictResolution(unittest.TestCase):
    def test_default_resolver_picks_latest_change(self):
        _, _, _, result = _diverged_doc()
        self.assertEqual(result.at("doc")["status"], "done")

    def test_default_tie_breaks_by_branch_name(self):
        base = ChangeLog(clock=lambda: 0.0)
        base.append("doc", "status", "draft", 1)
        zhang = fork(base, "zhang", clock=_clock([10.0]))
        zhang.log.append("doc", "status", "z", 2)
        li = fork(base, "li", clock=_clock([10.0]))
        li.log.append("doc", "status", "l", 2)
        result = merge("doc", base, [zhang, li], 1, clock=_clock([100.0]))
        self.assertEqual(result.at("doc")["status"], "l")  # li < zhang

    def test_loser_is_listed_with_its_branch(self):
        _, _, _, result = _diverged_doc()
        conflicts = result.conflicts("doc")
        self.assertEqual([c.field for c in conflicts], ["status"])
        conflict = conflicts[0]
        self.assertEqual(conflict.winner.change.value, "done")
        self.assertEqual(conflict.winner.branch.name, "zhang")
        self.assertEqual(len(conflict.losers), 1)
        self.assertEqual(conflict.losers[0].change.value, "review")
        self.assertEqual(conflict.losers[0].branch.name, "li")

    def test_losers_flattens_all_conflicts(self):
        _, _, _, result = _diverged_doc()
        self.assertEqual([c.value for c in result.losers("doc")], ["review"])

    def test_prefer_branch_strategy_overrides_default(self):
        base, zhang, li, _ = _diverged_doc()
        result = merge(
            "doc", base, [zhang, li], 1,
            resolver=prefer_branch("li"),
            clock=_clock([100.0, 101.0, 102.0]),
        )
        self.assertEqual(result.at("doc")["status"], "review")
        conflict = result.conflicts("doc")[0]
        self.assertEqual(conflict.winner.branch.name, "li")
        self.assertEqual(conflict.losers[0].change.value, "done")

    def test_custom_resolver_signature(self):
        # 消解函数签名：(field, candidates) -> 选中的 Candidate。
        # 业务口径示例：不看时钟，挑值字典序最小的。
        def smallest_value(field, candidates):
            return min(candidates, key=lambda c: c.change.value)

        base, zhang, li, _ = _diverged_doc()
        result = merge(
            "doc", base, [zhang, li], 1,
            resolver=smallest_value,
            clock=_clock([100.0, 101.0, 102.0]),
        )
        self.assertEqual(result.at("doc")["status"], "done")  # "done" < "review"

        seen = []

        def recording(field, candidates):
            seen.append(
                (field, [(c.branch.name, c.change.value) for c in candidates])
            )
            return last_write_wins(field, candidates)

        merge(
            "doc", base, [zhang, li], 1,
            resolver=recording,
            clock=_clock([100.0, 101.0, 102.0]),
        )
        status_call = next(item for item in seen if item[0] == "status")
        self.assertEqual(
            status_call[1], [("li", "review"), ("zhang", "done")]
        )

    def test_resolver_may_return_plain_change(self):
        def pick_li_change(field, candidates):
            li = [c for c in candidates if c.branch.name == "li"]
            return (li[0] if li else candidates[0]).change

        base, zhang, li, _ = _diverged_doc()
        result = merge(
            "doc", base, [zhang, li], 1,
            resolver=pick_li_change,
            clock=_clock([100.0, 101.0, 102.0]),
        )
        self.assertEqual(result.at("doc")["status"], "review")


class TestDelete(unittest.TestCase):
    def test_deleted_field_stays_gone_even_when_other_branch_edits_it(self):
        base, zhang, li = _delete_scenario()
        result = merge(
            "doc", base, [zhang, li], 1, clock=_clock([100.0, 101.0])
        )
        self.assertNotIn("title", result.at("doc"))

    def test_delete_history_shows_intermediate_edit(self):
        # 快照里没有该字段，但历史看得见“改过又被删”，且来源都在。
        base, zhang, li = _delete_scenario()
        result = merge(
            "doc", base, [zhang, li], 1, clock=_clock([100.0, 101.0])
        )
        title_entries = [m for m in result.history("doc") if m.field == "title"]
        self.assertEqual(
            [(m.value, m.sources) for m in title_entries[1:]],
            [("老张标题", ["zhang"]), (DELETE, ["li"])],
        )

    def test_delete_loser_is_accounted(self):
        base, zhang, li = _delete_scenario()
        result = merge(
            "doc", base, [zhang, li], 1, clock=_clock([100.0, 101.0])
        )
        conflict = result.conflicts("doc")[0]
        self.assertEqual(conflict.winner.change.value, DELETE)
        self.assertEqual(conflict.losers[0].change.value, "老张标题")
        self.assertEqual(result.losers("doc")[0].value, "老张标题")

    def test_custom_resolver_can_keep_edited_value(self):
        # 业务口径不同：自定义消解不要墓碑优先，编辑可以盖过删除。
        def edit_wins(field, candidates):
            alive = [c for c in candidates if c.change.value is not DELETE]
            return (alive or candidates)[0]

        base, zhang, li = _delete_scenario()
        result = merge(
            "doc", base, [zhang, li], 1,
            resolver=edit_wins, clock=_clock([100.0]),
        )
        self.assertEqual(result.at("doc"), {"title": "老张标题"})
        self.assertEqual(result.losers("doc")[0].value, DELETE)

    def test_at_old_version_filters_tombstones(self):
        base = ChangeLog(clock=lambda: 0.0)
        base.append("doc", "title", "草稿", 1)
        zhang = fork(base, "zhang", clock=_clock([10.0]))
        zhang.log.append("doc", "title", DELETE, 2)
        result = merge("doc", base, [zhang], 1, clock=_clock([100.0]))
        self.assertEqual(result.at("doc", 1), {"title": "草稿"})
        self.assertEqual(result.at("doc", 2), {})


def _delete_scenario():
    base = ChangeLog(clock=lambda: 0.0)
    base.append("doc", "title", "草稿", 1)
    zhang = fork(base, "zhang", clock=_clock([10.0]))
    zhang.log.append("doc", "title", "老张标题", 2)
    li = fork(base, "li", clock=_clock([20.0]))
    li.log.append("doc", "title", DELETE, 2)
    return base, zhang, li


class TestMergeValidation(unittest.TestCase):
    def test_duplicate_branch_names_rejected(self):
        base = ChangeLog(clock=lambda: 0.0)
        base.append("doc", "a", 1, 1)
        b1 = fork(base, "x", clock=lambda: 1.0)
        b2 = fork(base, "x", clock=lambda: 1.0)
        with self.assertRaises(ValueError):
            merge("doc", base, [b1, b2], 1)

    def test_merge_needs_a_branch(self):
        base = ChangeLog(clock=lambda: 0.0)
        with self.assertRaises(ValueError):
            merge("doc", base, [], 1)

    def test_candidate_exposes_branch_and_change(self):
        # 锁定自定义消解函数看到的 Candidate 形状。
        base = ChangeLog(clock=lambda: 0.0)
        base.append("doc", "a", 1, 1)
        zhang = fork(base, "zhang", clock=_clock([10.0]))
        zhang.log.append("doc", "a", 2, 2)
        captured = {}

        def grab(field, candidates):
            captured["candidate"] = candidates[0]
            return candidates[0]

        merge("doc", base, [zhang], 1, resolver=grab, clock=_clock([100.0]))
        candidate = captured["candidate"]
        self.assertIsInstance(candidate, Candidate)
        self.assertEqual(candidate.branch.name, "zhang")
        self.assertEqual(candidate.change.value, 2)


if __name__ == "__main__":
    unittest.main()
