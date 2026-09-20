"""多分支合并的行为测试（单线基线见 test_changelog.py，本文件只测新行为）。"""

import unittest

from changelogd.changelog import DELETED, Change, ChangeLog
from changelogd.merge import merge, resolve_left, resolve_right


def log_with_ts(start=0):
    """返回一个 ChangeLog，注入时钟从 start 起每次 +1。"""
    ticks = iter(range(start, start + 1000))
    return ChangeLog(clock=lambda: float(next(ticks)))


def replay(result):
    return result.apply_to(ChangeLog(clock=lambda: 0.0))


class TestDeleteSemantics(unittest.TestCase):
    def test_at_drops_deleted_field(self):
        log = log_with_ts()
        log.append("d", "a", 1, 1)
        log.append("d", "b", 2, 1)
        log.delete("d", "a", 2)
        self.assertEqual(log.at("d", 1), {"a": 1, "b": 2})
        self.assertEqual(log.at("d", 2), {"b": 2})

    def test_history_still_shows_delete(self):
        log = log_with_ts()
        log.append("d", "a", 1, 1)
        log.delete("d", "a", 2)
        self.assertEqual([c.value for c in log.history("d")], [1, DELETED])

    def test_delete_returns_record(self):
        log = log_with_ts()
        change = log.delete("d", "a", 3)
        self.assertIs(change.value, DELETED)
        self.assertEqual(change.version, 3)


class TestMergeDisjoint(unittest.TestCase):
    def test_disjoint_fields_merge_with_origin(self):
        base = log_with_ts()
        base.append("doc", "title", "草稿", 1)
        base.append("doc", "status", "draft", 1)
        left = log_with_ts(10)
        left.append("doc", "title", "定稿", 2)
        left.append("doc", "status", "review", 2)
        right = log_with_ts(20)
        right.append("doc", "tag", "release", 2)

        result = merge(base.history("doc"), left.history("doc"), right.history("doc"))

        self.assertEqual(result.conflicts, [])
        got = [(mc.origin, mc.change.field, mc.change.value) for mc in result.changes]
        self.assertEqual(
            got,
            [
                ("base", "title", "草稿"),
                ("base", "status", "draft"),
                ("left", "title", "定稿"),
                ("left", "status", "review"),
                ("right", "tag", "release"),
            ],
        )

    def test_changes_are_the_original_objects(self):
        left = log_with_ts(10)
        original = left.append("doc", "title", "定稿", 2)
        result = merge([], left.history("doc"), [])
        (entry,) = result.changes
        self.assertIs(entry.change, original)
        self.assertEqual(entry.change.ts, 10.0)
        self.assertEqual(entry.origin, "left")

    def test_merged_log_replays_to_expected_snapshot(self):
        base = log_with_ts()
        base.append("doc", "title", "草稿", 1)
        base.append("doc", "status", "draft", 1)
        left = log_with_ts(10)
        left.append("doc", "title", "定稿", 2)
        right = log_with_ts(20)
        right.append("doc", "tag", "release", 3)

        merged = replay(
            merge(base.history("doc"), left.history("doc"), right.history("doc"))
        )
        self.assertEqual(merged.at("doc", 1), {"title": "草稿", "status": "draft"})
        self.assertEqual(merged.at("doc", 2), {"title": "定稿", "status": "draft"})
        self.assertEqual(
            merged.at("doc", 3),
            {"title": "定稿", "status": "draft", "tag": "release"},
        )

    def test_same_final_value_is_not_a_conflict(self):
        left = log_with_ts(10)
        left.append("doc", "status", "done", 2)
        right = log_with_ts(20)
        right.append("doc", "status", "done", 2)
        result = merge([], left.history("doc"), right.history("doc"))
        self.assertEqual(result.conflicts, [])
        self.assertEqual([mc.origin for mc in result.changes], ["left"])


class TestMergeConflicts(unittest.TestCase):
    def _conflicting(self, left_v, left_ts, right_v, right_ts, **kwargs):
        left = ChangeLog(clock=lambda: left_ts)
        left.append("doc", "status", "left值", left_v)
        right = ChangeLog(clock=lambda: right_ts)
        right.append("doc", "status", "right值", right_v)
        return merge([], left.history("doc"), right.history("doc"), **kwargs)

    def test_default_newer_version_wins(self):
        result = self._conflicting(2, 99.0, 3, 1.0)
        (conflict,) = result.conflicts
        self.assertEqual(conflict.obj, "doc")
        self.assertEqual(conflict.field, "status")
        self.assertEqual(conflict.winner.origin, "right")
        self.assertEqual(conflict.winner.change.value, "right值")
        self.assertEqual(
            [(l.origin, l.change.value) for l in conflict.losers],
            [("left", "left值")],
        )
        self.assertEqual(result.losers, list(conflict.losers))
        self.assertEqual(replay(result).at("doc", 9), {"status": "right值"})

    def test_default_left_can_win(self):
        result = self._conflicting(5, 1.0, 2, 9.0)
        self.assertEqual(result.conflicts[0].winner.change.value, "left值")

    def test_default_tie_breaks_by_ts_then_right(self):
        result = self._conflicting(2, 1.0, 2, 2.0)
        self.assertEqual(result.conflicts[0].winner.change.value, "right值")
        result = self._conflicting(2, 5.0, 2, 5.0)
        self.assertEqual(result.conflicts[0].winner.change.value, "right值")

    def test_builtin_strategies_are_swappable(self):
        result = self._conflicting(2, 0.0, 9, 0.0, resolve=resolve_left)
        self.assertEqual(result.conflicts[0].winner.change.value, "left值")
        result = self._conflicting(9, 0.0, 2, 0.0, resolve=resolve_right)
        self.assertEqual(result.conflicts[0].winner.change.value, "right值")

    def test_custom_resolver_picks_side(self):
        result = self._conflicting(2, 0.0, 3, 0.0, resolve=lambda f, l, r: l)
        self.assertEqual(result.conflicts[0].winner.change.value, "left值")

    def test_custom_resolver_can_synthesize_value(self):
        def concat(field, left, right):
            return Change(
                left.obj, field, f"{left.value}+{right.value}",
                max(left.version, right.version), 0.0,
            )

        result = self._conflicting(2, 0.0, 3, 0.0, resolve=concat)
        (conflict,) = result.conflicts
        self.assertEqual(conflict.winner.origin, "resolved")
        self.assertEqual(conflict.winner.change.value, "left值+right值")
        self.assertEqual(len(conflict.losers), 2)
        self.assertEqual(replay(result).at("doc", 9), {"status": "left值+right值"})


class TestMergeDelete(unittest.TestCase):
    def test_delete_beats_modify_and_stays_out_of_snapshot(self):
        base = log_with_ts()
        base.append("doc", "note", "旧备注", 1)
        left = log_with_ts(10)
        left.delete("doc", "note", 2)
        right = log_with_ts(20)
        right.append("doc", "note", "小李改的备注", 3)

        result = merge(base.history("doc"), left.history("doc"), right.history("doc"))

        (conflict,) = result.conflicts
        self.assertEqual(conflict.field, "note")
        self.assertEqual(conflict.winner.origin, "left")
        self.assertIs(conflict.winner.change.value, DELETED)
        self.assertEqual([l.change.value for l in conflict.losers], ["小李改的备注"])

        merged = replay(result)
        self.assertEqual(merged.at("doc", 9), {})
        # 历史里看得见删除全程，被消解的修改记在台账里
        self.assertEqual([c.value for c in merged.history("doc")], ["旧备注", DELETED])
        self.assertEqual(result.losers[0].change.value, "小李改的备注")

    def test_both_sides_delete_is_not_a_conflict(self):
        base = log_with_ts()
        base.append("doc", "note", "旧", 1)
        left = log_with_ts(10)
        left.delete("doc", "note", 2)
        right = log_with_ts(20)
        right.delete("doc", "note", 2)
        result = merge(base.history("doc"), left.history("doc"), right.history("doc"))
        self.assertEqual(result.conflicts, [])
        self.assertEqual(replay(result).at("doc", 9), {})

    def test_delete_then_readd_same_branch_keeps_full_trail(self):
        base = log_with_ts()
        base.append("doc", "note", "旧", 1)
        left = log_with_ts(10)
        left.delete("doc", "note", 2)
        left.append("doc", "note", "重新写的", 4)
        result = merge(base.history("doc"), left.history("doc"), [])
        merged = replay(result)
        self.assertEqual(merged.at("doc", 9), {"note": "重新写的"})
        self.assertEqual(
            [c.value for c in merged.history("doc")], ["旧", DELETED, "重新写的"]
        )


class TestForkAndMergeStory(unittest.TestCase):
    def test_zhang_and_li(self):
        base = log_with_ts()
        base.append("doc", "title", "草稿", 1)
        base.append("doc", "status", "draft", 1)
        zhang = log_with_ts(10)  # 老张：改标题和状态
        zhang.append("doc", "title", "定稿", 2)
        zhang.append("doc", "status", "review", 2)
        li = log_with_ts(20)  # 小李：也动状态，补个标签
        li.append("doc", "status", "published", 3)
        li.append("doc", "tag", "release", 3)

        result = merge(base.history("doc"), zhang.history("doc"), li.history("doc"))

        (conflict,) = result.conflicts
        self.assertEqual(conflict.field, "status")
        self.assertEqual(conflict.winner.change.value, "published")  # v3 更新
        self.assertEqual(conflict.losers[0].change.value, "review")

        merged = replay(result)
        self.assertEqual(
            merged.at("doc", 9),
            {"title": "定稿", "status": "published", "tag": "release"},
        )
        # 每条合并结果都能说清来自哪条分支
        origins = {
            mc.change.field: mc.origin
            for mc in result.changes
            if mc.change.version > 1
        }
        self.assertEqual(origins, {"title": "left", "status": "right", "tag": "right"})


if __name__ == "__main__":
    unittest.main()
