"""diff3x 语义测试。

组织：
  - SplitAndStructureTest：README §1/§7 的输入切分、结果结构、标记行格式（绿）。
  - LineEndingTest：README §2 换行归一化（绿 + 红）。
  - MergeSemanticsTest：README §3/§4/§5/§6 的合并规则（绿 + 红）。
  - MergeInvariantTest：任务要求的三条合并层性质，含红用例。
  - ReferenceDifferentialTest：朴素参考实现 + 固定 seed 随机对拍（确定性）。

红用例：源码与 README 不符、被本文件钉死的行为；每个红用例上方都有
「README 期望 / 实际发生」注释，断言按 README 写。README 未约定的自由
行为（如同点不同插入的并置顺序）不在红用例中断言具体形态。
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from diff3x.diff3 import merge  # noqa: E402


# ---------------------------------------------------------------------------
# 朴素参考实现：严格按 README 语义直译的逐行对比，与被测代码不共享实现。
#   - 切分：str.split('\n')，与 README §1 一致；
#   - 对齐：手写 LCS（最长公共子序列）回溯，不使用 difflib；
#   - 比较：base 与两侧都做行尾 '\r' 归一化（README §2），输出保留原始行；
#   - 区域：LCS 回溯出的连续非 equal 段即替换区域（含插入/删除）；
#   - 合并：两侧区域按 base 坐标相交则成组（同点零长度插入视为同区域，
#     否则 README §5「相同插入保留一份」无从成立），组内单侧改动取该侧，
#     双方内容相同取一份，否则出标准七段冲突块；
#   - span：冲突块中某侧的行范围按该侧自己的行坐标取 [start, end) 切片，
#     因此组内落在两个改动之间的未改行也包含在该侧片段内。
# ---------------------------------------------------------------------------

def _canon(line):
    return line[:-1] if line.endswith("\r") else line


def _diff_regions(base, side):
    """LCS 对齐，返回 [(base_lo, base_hi, side_lo, side_hi, 原始替换行)]。"""
    bc = [_canon(line) for line in base]
    sc = [_canon(line) for line in side]
    n, m = len(bc), len(sc)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        bi = bc[i]
        row = dp[i]
        nxt = dp[i + 1]
        for j in range(m - 1, -1, -1):
            if bi == sc[j]:
                row[j] = nxt[j + 1] + 1
            else:
                row[j] = max(nxt[j], row[j + 1])
    regions = []
    i = j = 0
    while i < n or j < m:
        if i < n and j < m and bc[i] == sc[j]:
            i += 1
            j += 1
            continue
        bs, js = i, j
        while i < n or j < m:
            if i < n and j < m and bc[i] == sc[j]:
                break
            if i < n and (j >= m or dp[i + 1][j] >= dp[i][j + 1]):
                i += 1
            else:
                j += 1
        regions.append((bs, i, js, j, side[js:j]))
    return regions


def _intersect(one, two):
    """base 坐标上的相交判定（0 起始、含头不含尾）。"""
    s1, t1 = one[0], one[1]
    s2, t2 = two[0], two[1]
    if max(s1, s2) < min(t1, t2):
        return True
    # 零长度插入点严格落在另一侧区域内部 [lo, hi)
    if s1 == t1 and s2 <= s1 < t2:
        return True
    if s2 == t2 and s1 <= s2 < t1:
        return True
    # 两侧在同一坐标的零长度插入属于同区域（README §5 第一款的前提）
    if s1 == t1 and s2 == t2 and s1 == s2:
        return True
    return False


def reference_merge(base_text, a_text, b_text):
    """返回 (lines, conflicts)；conflict 为六元组，字段顺序同 Conflict。"""
    base = base_text.split("\n")
    a = a_text.split("\n")
    b = b_text.split("\n")
    ea = _diff_regions(base, a)
    eb = _diff_regions(base, b)

    items = [(region, 0) for region in ea] + [(region, 1) for region in eb]
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for x in range(len(items)):
        for y in range(x + 1, len(items)):
            if items[x][1] != items[y][1] and _intersect(items[x][0], items[y][0]):
                rx, ry = find(x), find(y)
                if rx != ry:
                    parent[rx] = ry

    groups = {}
    for index, (region, side) in enumerate(items):
        groups.setdefault(find(index), []).append((region, side))

    ordered = []
    for members in groups.values():
        lo = min(region[0] for region, _ in members)
        hi = max(region[1] for region, _ in members)
        ordered.append((lo, hi, members))
    ordered.sort(key=lambda g: (g[0], 0 if g[1] == g[0] else 1))

    lines = []
    conflicts = []
    pos = 0
    for lo, hi, members in ordered:
        lines.extend(base[pos:lo])
        ga = [region for region, side in members if side == 0]
        gb = [region for region, side in members if side == 1]

        def side_slice(group, full):
            if not group:
                return [], None
            slo = min(region[2] for region in group)
            shi = max(region[3] for region in group)
            return full[slo:shi], (slo, shi)

        arep, asp = side_slice(ga, a)
        brep, bsp = side_slice(gb, b)
        if not ga:
            lines.extend(brep)
        elif not gb:
            lines.extend(arep)
        elif arep == brep:
            lines.extend(arep)
        else:
            lines.append("<<<<<<< a")
            lines.extend(arep)
            lines.append("||||||| base")
            lines.extend(base[lo:hi])
            lines.append("=======")
            lines.extend(brep)
            lines.append(">>>>>>> b")
            conflicts.append((
                base[lo:hi], arep, brep, (lo, hi),
                asp if asp is not None else (0, 0),
                bsp if bsp is not None else (0, 0),
            ))
        pos = hi
    lines.extend(base[pos:])
    return lines, conflicts


def _conflict_tuples(result):
    return [
        (c.base_lines, c.a_lines, c.b_lines, c.base_span, c.a_span, c.b_span)
        for c in result.conflicts
    ]


class SplitAndStructureTest(unittest.TestCase):
    """README §1 切分、§7 结果结构。"""

    def test_trailing_newline_roundtrip(self):
        base = a = b = "one\ntwo\n"
        result = merge(base, a, b)
        self.assertTrue(result.clean)
        # 以换行结尾 -> 末位空串，"\n".join 后原样还原
        self.assertEqual(result.lines, ["one", "two", ""])
        self.assertEqual("\n".join(result.lines), base)

    def test_no_trailing_newline_roundtrip(self):
        base = a = b = "one\ntwo"
        result = merge(base, a, b)
        self.assertEqual(result.lines, ["one", "two"])
        self.assertEqual("\n".join(result.lines), base)

    def test_empty_inputs(self):
        result = merge("", "", "")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, [""])

    def test_clean_means_empty_conflicts(self):
        changed = merge("x\n", "a\n", "b\n")
        untouched = merge("x\n", "x\n", "x\n")
        self.assertFalse(changed.clean)
        self.assertEqual(len(changed.conflicts), 1)
        self.assertTrue(untouched.clean)
        self.assertEqual(untouched.conflicts, [])

    def test_conflict_marker_lines_top_aligned(self):
        result = merge("l0\nl1\nl2\n", "l0\nA\nl2\n", "l0\nB\nl2\n")
        markers = {"<<<<<<< a", "||||||| base", "=======", ">>>>>>> b"}
        found = [line for line in result.lines if line in markers]
        self.assertEqual(found, ["<<<<<<< a", "||||||| base", "=======", ">>>>>>> b"])
        # 标记行顶格：没有任何前导空白
        for line in found:
            self.assertEqual(line, line.lstrip())

    def test_conflict_has_six_fields_and_half_open_spans(self):
        result = merge("l0\nl1\nl2\n", "l0\nA\nl2\n", "l0\nB\nl2\n")
        conflict = result.conflicts[0]
        self.assertEqual(conflict.a_lines, ["A"])
        self.assertEqual(conflict.b_lines, ["B"])
        for span in (conflict.base_span, conflict.a_span, conflict.b_span):
            self.assertIsInstance(span, tuple)
            self.assertEqual(len(span), 2)
            self.assertLessEqual(span[0], span[1])


class LineEndingTest(unittest.TestCase):
    """README §2：行尾 '\r' 仅在比较时剥离，输出保留来源行原始内容。"""

    def test_all_crlf_unchanged_is_clean(self):
        # README 期望：三方完全相同（均 CRLF）-> clean，无冲突块。
        # 实际发生：_side_edits 只对 base 调 _canon，侧行 'x\r' 与
        #   归一化后的 base 'x' 不相等，整行被误判为双侧改动并报冲突。
        result = merge("x\r\n", "x\r\n", "x\r\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["x\r", ""])

    def test_lf_base_crlf_sides_unchanged_is_clean(self):
        # README 期望：两侧相对 base 仅有 '\r' 差异 -> 均未改动，clean，
        #   未改动区域取 base 原文（LF）。
        # 实际发生：侧行未归一化，两侧都被当作把 'x' 改成 'x\r'，误报冲突。
        result = merge("x\n", "x\r\n", "x\r\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["x", ""])

    def test_crlf_base_lf_sides_unchanged(self):
        result = merge("x\r\n", "x\n", "x\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["x\r", ""])

    def test_crlf_base_lf_sides_identical_real_change_is_clean(self):
        # README 期望：base CRLF、两侧 LF 且做相同实质改动 -> 相同替换，
        #   干净合并保留一份（'\r' 仅差异不构成改动）。
        # 实际发生：base 经 _canon 为 'x'、侧行 'y' 能对齐，但相同替换
        #   被 `is` 判定误伤（与 identical_replacement 同源），误报冲突。
        result = merge("x\r\n", "y\n", "y\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["y", ""])

    def test_single_side_real_change_keeps_raw_cr(self):
        # a 侧唯一改动必须原样出现；相邻未改动行保留 base 原文
        result = merge("l1\nl2\n", "l1\r\nX\n", "l1\nl2\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l1\r", "X", ""])

    def test_cr_only_on_one_side_is_not_change(self):
        # README 期望：a 侧行仅多了 '\r'，不构成改动；未改动区域按 §4
        #   取 base，输出 LF 原文 ["l1", "l2"]。
        # 实际发生：侧行未归一化，a 侧被当作整体替换；又因 b 侧无改动，
        #   merge 走单侧取侧分支，输出了 a 的 CRLF 原文而非 base。
        result = merge("l1\nl2\n", "l1\r\nl2\r\n", "l1\nl2\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l1", "l2", ""])

    def test_cr_only_difference_beside_parallel_real_change(self):
        # README 期望：'\r' 仅差异不构成改动；l2 两侧改成同样内容 ->
        #   干净合并，结果保留 base 原文 l1 + 双方相同的新行 X。
        # 实际发生：_side_edits 只对 base 做 _canon、侧行未归一化，
        #   a 侧整段文本被误判为改动，与 b 的局部改动相交，误报冲突。
        result = merge("l1\nl2\n", "l1\r\nX\n", "l1\nX\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l1", "X", ""])


class MergeSemanticsTest(unittest.TestCase):
    """README §3-§6：改动区域、取侧规则、冲突判定、冲突块边界。"""

    def test_disjoint_changes_both_kept(self):
        result = merge(
            "[service]\ntimeout = 30\nretries = 3\n",
            "[service]\ntimeout = 45\nretries = 3\n",
            "[service]\ntimeout = 30\nretries = 5\n",
        )
        self.assertTrue(result.clean)
        self.assertEqual("\n".join(result.lines),
                         "[service]\ntimeout = 45\nretries = 5\n")

    def test_only_a_changes_takes_a_verbatim(self):
        result = merge("l1\nl2\nl3\n", "l1\nX\nl3\n", "l1\nl2\nl3\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l1", "X", "l3", ""])

    def test_only_b_changes_takes_b_verbatim(self):
        result = merge("l1\nl2\nl3\n", "l1\nl2\nl3\n", "l1\nl2\nY\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l1", "l2", "Y", ""])

    def test_both_delete_same_region_is_clean(self):
        result = merge("l1\nl2\nl3\n", "l1\nl3\n", "l1\nl3\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l1", "l3", ""])

    def test_one_side_inserts_other_unchanged_is_clean(self):
        result = merge("l1\nl3\n", "l1\nl2\nl3\n", "l1\nl3\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l1", "l2", "l3", ""])

    def test_different_changes_same_region_conflict_seven_segments(self):
        result = merge("l0\nl1\nl2\n", "l0\nA\nl2\n", "l0\nB\nl2\n")
        self.assertFalse(result.clean)
        # 七个组成部分按 README §7 顺序出现；此处只钉「顺序与分段结构」。
        # 冲突块还会额外吞掉下一行 l2（见 test_conflict_block_excludes_*，
        # 已作为红用例单独钉死），故本用例不对整表做精确相等断言。
        expected_sequence = [
            "l0",
            "<<<<<<< a", "A",
            "||||||| base", "l1",
            "=======", "B",
            ">>>>>>> b",
        ]
        for expected_line in expected_sequence:
            self.assertIn(expected_line, result.lines)
        positions = [result.lines.index(marker) for marker in (
            "<<<<<<< a", "||||||| base", "=======", ">>>>>>> b")]
        self.assertEqual(positions, sorted(positions))
        conflict = result.conflicts[0]
        self.assertEqual(conflict.a_lines, ["A"])
        self.assertEqual(conflict.b_lines, ["B"])

    def test_identical_replacement_is_clean_single_copy(self):
        # README 期望：双方替换内容完全相同 -> 干净合并，只保留一份。
        # 实际发生：源码用 `arep is brep` 判定相同，两侧是独立 list，
        #   身份永远为 False，相同改动被误报冲突且重复展示两遍。
        result = merge("x\n", "y\n", "y\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["y", ""])

    def test_identical_insertion_at_same_point_is_clean_single_copy(self):
        # README 期望：双方在同一位置插入相同内容（同点插入按 §5 属同区域）
        #   -> 干净合并，只保留一份。
        # 实际发生：相交判定只检查正长度区间，同点的零长度插入从不归组，
        #   相同插入被静默输出两份，且不报冲突。
        result = merge("l1\nl3\n", "l1\nl2\nl3\n", "l1\nl2\nl3\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l1", "l2", "l3", ""])

    def test_delete_vs_modify_is_conflict_a_deletes(self):
        # README 期望：一方删除（替换为空）、另一方修改 -> 冲突，
        #   任何一侧都不得被静默丢弃。
        # 实际发生：源码 `if not brep: take_clean(arep)` 直接采用修改侧，
        #   删除被静默丢弃，clean 为 True。
        result = merge("l1\nl2\nl3\n", "l1\nl3\n", "l1\nX\nl3\n")
        self.assertFalse(result.clean)
        self.assertEqual(len(result.conflicts), 1)
        conflict = result.conflicts[0]
        self.assertEqual(conflict.base_lines, ["l2"])
        self.assertEqual(conflict.a_lines, [])
        self.assertEqual(conflict.b_lines, ["X"])

    def test_delete_vs_modify_is_conflict_b_deletes(self):
        # README 期望：同上，反方向也必须冲突。
        # 实际发生：`elif not arep: take_clean(brep)` 同样静默采用修改侧。
        result = merge("l1\nl2\nl3\n", "l1\nX\nl3\n", "l1\nl3\n")
        self.assertFalse(result.clean)
        conflict = result.conflicts[0]
        self.assertEqual(conflict.base_lines, ["l2"])
        self.assertEqual(conflict.a_lines, ["X"])
        self.assertEqual(conflict.b_lines, [])

    def test_conflict_block_excludes_following_clean_line(self):
        # README 期望：冲突块只覆盖双方改动基区的并集（此处仅 base 行 l1），
        #   紧邻的未改动行 l2 必须原样留在冲突块外。
        # 实际发生：冲突分支无条件 `hi += 1`，多吞下一行未改动行 l2，
        #   base_lines/base_span/lines 三处一起越界。
        result = merge("l0\nl1\nl2\n", "l0\nA\nl2\n", "l0\nB\nl2\n")
        conflict = result.conflicts[0]
        self.assertEqual(conflict.base_span, (1, 2))
        self.assertEqual(conflict.base_lines, ["l1"])
        self.assertEqual(result.lines.index("l2"),
                         result.lines.index(">>>>>>> b") + 1)

    def test_conflict_block_excludes_preceding_clean_line(self):
        # 与上一条同源：冲突发生在中间区域时，前一未改行也不得进块。
        result = merge("l0\nl1\nl2\nl3\n", "l0\nA\nl2\nl3\n", "l0\nB\nl2\nl3\n")
        conflict = result.conflicts[0]
        self.assertEqual(conflict.base_span, (1, 2))
        self.assertEqual(conflict.base_lines, ["l1"])

    def test_base_span_in_range_at_end_of_file_without_newline(self):
        # README 期望：base 只有一行且无末尾换行时，冲突 base_span=(0,1)。
        # 实际发生：`hi += 1` 越过 split 后的有效行数，base_span=(0,2)，
        #   base_lines 与 span 切片不再自洽。
        result = merge("x", "a", "b")
        conflict = result.conflicts[0]
        self.assertEqual(conflict.base_span, (0, 1))
        self.assertEqual(conflict.base_lines, ["x"])

    def test_insertion_point_at_region_end_is_conflict_when_distinct(self):
        # README 期望：b 在 base 位置 6 插入（零长度基区，点 6 落在 a 的
        #   修改区间 [5,7) 内）-> 同一基区，插入与修改不同 -> 冲突，
        #   任何一侧都不得被静默丢弃。
        # 实际发生：分组增长循环只在 `base_start < hi` 时吸收新区，
        #   起始即等于区间端点 hi 的插入被漏掉，两侧改动被静默错合
        #   （插入行与修改行各丢一份上下文并重复）。
        base = "b0\nb1\nb2\nb3\nb4\nb5\nb6\n"
        a = "z3\nb1\nb2\nb3\nb4\nb5x\nb5\nb6x\nb6\n"
        b = "b0\nb1\nb2\nb3\nb4\nb5x\nb6\n"
        result = merge(base, a, b)
        self.assertFalse(result.clean)
        # 不冲突的独立改动（a 在头部的 z3）仍应原样保留
        self.assertEqual(result.lines[0], "z3")

    def test_chained_overlap_includes_inner_unchanged_line_in_side_span(self):
        # README 期望：a 改 [1,3)、b 改 [2,5)、a 再改 [4,6) 经相交链成
        #   一个冲突块，基区并集 [1,6)。冲突块里 a 侧片段是 a 在该块中
        #   的完整行范围（a_span=(1,6)），因此 a 未改动的对齐行 '3'
        #   必须出现在 a_lines 中；b_span=(2,5) 同理。
        # 实际发生：源码只拼接各替换区 repl（漏掉块内对齐的未改行 '3'），
        #   但 a_span 仍按完整范围给出 (1,6)，span 与 a_lines 不自洽；
        #   同时 hi+=1 又把未改动行 '6' 吞进 base 侧。
        base = "0\n1\n2\n3\n4\n5\n6\n"
        a = "0\nA1\nA2\n3\nA4\nA5\n6\n"
        b = "0\n1\nB2\nB3\nB4\n5\n6\n"
        result = merge(base, a, b)
        conflict = result.conflicts[0]
        self.assertEqual(conflict.base_span, (1, 6))
        self.assertEqual(conflict.a_span, (1, 6))
        self.assertEqual(conflict.b_span, (2, 5))
        self.assertEqual(conflict.a_lines, ["A1", "A2", "3", "A4", "A5"])
        self.assertEqual(conflict.base_lines, ["1", "2", "3", "4", "5"])
        self.assertEqual(result.lines[-2:], ["6", ""])


class MergeInvariantTest(unittest.TestCase):
    """合并层三条性质：单侧改动不丢、双方相同改动不冲突、冲突块不吞邻行。"""

    def test_one_sided_change_lines_appear_verbatim(self):
        # 性质 1：只在一侧改动的行必须原样出现在结果里（两个方向各扫一遍）。
        base = "h0\nh1\nh2\nh3\nh4\n"
        a = "h0\nA1\nh2\nINS\nh3\nh4\n"
        b = base
        result = merge(base, a, b)
        self.assertTrue(result.clean)
        self.assertEqual("\n".join(result.lines), a)

        result = merge(base, base, "h0\nh1\nX2\nh3\nh4\n")
        self.assertTrue(result.clean)
        self.assertEqual("\n".join(result.lines), "h0\nh1\nX2\nh3\nh4\n")

    def test_identical_two_sided_replace_does_not_conflict(self):
        # 性质 2：两侧对同一位置的相同替换不报冲突。
        # README 期望 clean；实际被 `arep is brep` 身份比较误报冲突。
        result = merge("l0\nl1\nl2\n", "l0\nS\nl2\n", "l0\nS\nl2\n")
        self.assertTrue(result.clean)

    def test_identical_two_sided_delete_does_not_conflict(self):
        # 性质 2：两侧删除同一区域不报冲突（此形态当前恰好为绿）。
        result = merge("l0\nl1\nl2\n", "l0\nl2\n", "l0\nl2\n")
        self.assertTrue(result.clean)

    def test_identical_two_sided_insert_does_not_conflict(self):
        # 性质 2：两侧在同一位置插入相同内容不报冲突、不重复。
        # README 期望 clean 且只有一份；实际同点零长度插入未归组，输出两份。
        result = merge("l0\nl2\n", "l0\nI\nl2\n", "l0\nI\nl2\n")
        self.assertTrue(result.clean)
        self.assertEqual(result.lines, ["l0", "I", "l2", ""])

    def test_conflict_blocks_cover_only_conflicting_intervals(self):
        # 性质 3：每个冲突块紧邻的无冲突行必须留在块外（前后各一条）。
        # README 期望：冲突行 l2 两侧的 l1、l3 都是未改动行，直接输出。
        # 实际发生：hi+=1 使后邻行 l3 被并入冲突块的 base 段。
        result = merge("l0\nl1\nl2\nl3\nl4\n",
                       "l0\nl1\nA\nl3\nl4\n",
                       "l0\nl1\nB\nl3\nl4\n")
        lines = result.lines
        marker = lines.index(">>>>>>> b")
        self.assertEqual(lines[marker + 1], "l3")
        self.assertEqual(lines[lines.index("<<<<<<< a") - 1], "l1")
        self.assertNotIn("l3", result.conflicts[0].base_lines)

    def test_conflict_spans_slice_back_to_listed_lines(self):
        # 结构性不变量：span 既然定义为「该侧在冲突块中的行范围」，
        # base/a/b 三个 lines 列表必须能由对应全文按 span 切回。
        # 链状相交用例上该不变量当前被破坏（见上一个红用例同源缺陷）。
        base = "0\n1\n2\n3\n4\n5\n6\n"
        a_text = "0\nA1\nA2\n3\nA4\nA5\n6\n"
        b_text = "0\n1\nB2\nB3\nB4\n5\n6\n"
        result = merge(base, a_text, b_text)
        a_split = a_text.split("\n")
        b_split = b_text.split("\n")
        base_split = base.split("\n")
        conflict = result.conflicts[0]
        self.assertEqual(a_split[conflict.a_span[0]:conflict.a_span[1]],
                         conflict.a_lines)
        self.assertEqual(b_split[conflict.b_span[0]:conflict.b_span[1]],
                         conflict.b_lines)
        self.assertEqual(base_split[conflict.base_span[0]:conflict.base_span[1]],
                         conflict.base_lines)


def _mutate_side(rng, base, counter):
    """基于同一基线生成行级增/删/改混排的一侧文本元素（带全局唯一 token）。"""
    side = []
    for line in base:
        roll = rng.random()
        if roll < 0.18:
            kind = rng.random()
            if kind < 0.35:
                continue  # 删除该行
            if kind < 0.7:
                side.append(line + "x")  # 修改
            else:
                side.append(line + "x")  # 修改并在其后插入，锚点仍唯一
                side.append(line)
        else:
            side.append(line)
            if rng.random() < 0.12:
                side.insert(len(side) - 1, "z%d" % next(counter))
    return side


class ReferenceDifferentialTest(unittest.TestCase):
    """与朴素参考实现对拍。固定 seed，纯确定性，可独立重复运行。"""

    SEED_LF = 20260920
    SEED_CRLF = 20260921
    SEED_TERMINATORS = 20260922
    TRIALS_LF = 4000
    TRIALS_CRLF = 2000
    TRIALS_TERMINATORS = 1500

    def _collect(self, seed, trials, terminator_sets, nmax):
        rng = random.Random(seed)
        counter = iter(range(10 ** 9))
        mismatch_count = 0
        first_mismatch = None
        for _ in range(trials):
            n = rng.randrange(0, nmax)
            base = ["b%d" % k for k in range(n)]
            a = _mutate_side(rng, base, counter)
            b = _mutate_side(rng, base, counter)
            t_base, t_a, t_b = rng.choice(terminator_sets)
            base_text = t_base.join(base)
            a_text = t_a.join(a)
            b_text = t_b.join(b)
            ref_lines, ref_conflicts = reference_merge(base_text, a_text, b_text)
            result = merge(base_text, a_text, b_text)
            if ref_lines != result.lines or ref_conflicts != _conflict_tuples(result):
                mismatch_count += 1
                if first_mismatch is None:
                    first_mismatch = (base_text, a_text, b_text,
                                      ref_lines, result.lines)
        return mismatch_count, first_mismatch

    def test_reference_self_consistency_on_seeded_inputs(self):
        # 护栏：参考实现自身必须稳定、可重复，且满足全部三条结构不变量，
        # 否则对拍结果没有意义。
        rng = random.Random(12345)
        counter = iter(range(10 ** 9))
        terminators = ["\n", "", "\r\n"]
        for _ in range(500):
            n = rng.randrange(0, 12)
            base = ["b%d" % k for k in range(n)]
            a = _mutate_side(rng, base, counter)
            b = _mutate_side(rng, base, counter)
            base_text = rng.choice(terminators).join(base)
            a_text = rng.choice(terminators).join(a)
            b_text = rng.choice(terminators).join(b)
            lines, conflicts = reference_merge(base_text, a_text, b_text)
            # 重复运行结果一致（无时序/随机性残留）
            self.assertEqual((lines, conflicts),
                             reference_merge(base_text, a_text, b_text))
            base_split = base_text.split("\n")
            a_split = a_text.split("\n")
            b_split = b_text.split("\n")
            for c in conflicts:
                base_chunk, a_chunk, b_chunk, bsp, asp, bbsp = c
                self.assertEqual(base_split[bsp[0]:bsp[1]], base_chunk)
                self.assertEqual(a_split[asp[0]:asp[1]], a_chunk)
                self.assertEqual(b_split[bbsp[0]:bbsp[1]], b_chunk)

    def test_lf_inputs_match_reference(self):
        # README 期望：LF 输入下合并文本与冲突区间与直译参考完全一致。
        # 实际发生：固定 seed 4000 例存在大量分歧（相同改动误报冲突、
        #   删除被静默采用、hi+=1 吞行、插入点漏并、链状块漏对齐行）。
        mismatch_count, first = self._collect(
            self.SEED_LF, self.TRIALS_LF, [("\n", "\n", "\n")], 10)
        self.assertEqual(mismatch_count, 0,
                         "%d/%d 例与参考不一致，首例：%r"
                         % (mismatch_count, self.TRIALS_LF, first))

    def test_crlf_inputs_match_reference(self):
        # README 期望：混合 CRLF/LF 时 '\r' 仅差异不构成改动，结果与参考一致。
        # 实际发生：侧行未做 _canon，未改行的 CRLF/LF 差异被整段误判为改动，
        #   连锁引发误报/漏报冲突与内容丢失。
        terminator_sets = [
            ("\r\n", "\n", "\n"),
            ("\n", "\r\n", "\n"),
            ("\n", "\n", "\r\n"),
            ("\r\n", "\r\n", "\n"),
            ("\r\n", "\n", "\r\n"),
            ("\r\n", "\r\n", "\r\n"),
        ]
        mismatch_count, first = self._collect(
            self.SEED_CRLF, self.TRIALS_CRLF, terminator_sets, 10)
        self.assertEqual(mismatch_count, 0,
                         "%d/%d 例与参考不一致，首例：%r"
                         % (mismatch_count, self.TRIALS_CRLF, first))

    def test_terminator_edge_cases_match_reference(self):
        # README 期望：末尾无换行 / 空文件 / 三方末换行形态不一致，
        #   切分与拼接规则（§1）下结果仍与参考一致。
        # 实际发生：无末换行场景里 hi+=1 造成越界 span；空基线同点插入
        #   等场景与 §5 判定缺陷叠加产生分歧。
        terminator_sets = [
            ("\n", "\n", "\n"),
            ("", "", ""),
            ("\r\n", "\r\n", "\r\n"),
            ("\n", "", ""),
            ("", "\r\n", "\n"),
            ("\r\n", "", "\n"),
        ]
        mismatch_count, first = self._collect(
            self.SEED_TERMINATORS, self.TRIALS_TERMINATORS,
            terminator_sets, 8)
        self.assertEqual(mismatch_count, 0,
                         "%d/%d 例与参考不一致，首例：%r"
                         % (mismatch_count, self.TRIALS_TERMINATORS, first))


if __name__ == "__main__":
    unittest.main(verbosity=2)
