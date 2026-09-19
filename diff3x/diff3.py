"""三方文本合并（diff3）。

以 base 为坐标归并 a、b 两侧改动：干净合并，或产出结构化冲突块。
语义约定见 README，本文件与 README 如有出入，以 README 为准。
"""

from difflib import SequenceMatcher


class Conflict:
    """一个冲突块。span 为 0 起始、含头不含尾的 (start, end) 行区间。"""

    def __init__(self, base_lines, a_lines, b_lines, base_span, a_span, b_span):
        self.base_lines = base_lines
        self.a_lines = a_lines
        self.b_lines = b_lines
        self.base_span = base_span
        self.a_span = a_span
        self.b_span = b_span

    def __repr__(self):
        return "<Conflict base=%r a=%r b=%r>" % (self.base_span, self.a_span, self.b_span)


class MergeResult:
    """merge 的返回值；clean 等价于 conflicts 为空。"""

    def __init__(self, lines, conflicts):
        self.lines = lines
        self.conflicts = conflicts

    @property
    def clean(self):
        return not self.conflicts


class _Edit:
    """单侧一处改动：base 的 [base_start, base_end) 替换为 repl；side_start 为该侧行号。"""

    __slots__ = ("base_start", "base_end", "repl", "side_start")

    def __init__(self, base_start, base_end, repl, side_start):
        self.base_start = base_start
        self.base_end = base_end
        self.repl = repl
        self.side_start = side_start


def _canon(lines):
    """剥离行尾 \\r，用于比较。"""
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def _side_edits(base_lines, side_lines):
    """side 相对 base 的改动列表，按 base 坐标升序。"""
    sm = SequenceMatcher(a=_canon(base_lines), b=side_lines, autojunk=False)
    edits = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            edits.append(_Edit(i1, i2, side_lines[j1:j2], j1))
    return edits


def _span(grp):
    if not grp:
        return None
    return (grp[0].side_start, grp[-1].side_start + len(grp[-1].repl))


def merge(base, a, b):
    base_lines = base.split("\n")
    a_lines = a.split("\n")
    b_lines = b.split("\n")
    a_edits = _side_edits(base_lines, a_lines)
    b_edits = _side_edits(base_lines, b_lines)

    out = []
    conflicts = []
    pos = 0

    def take_clean(lo, hi, repl):
        nonlocal pos
        out.extend(base_lines[pos:lo])
        out.extend(repl)
        pos = hi

    i = j = 0
    while i < len(a_edits) or j < len(b_edits):
        if j >= len(b_edits) or (i < len(a_edits) and a_edits[i].base_end <= b_edits[j].base_start):
            e = a_edits[i]
            take_clean(e.base_start, e.base_end, e.repl)
            i += 1
            continue
        if i >= len(a_edits) or b_edits[j].base_end <= a_edits[i].base_start:
            e = b_edits[j]
            take_clean(e.base_start, e.base_end, e.repl)
            j += 1
            continue
        # 两侧改动相交，先吸收成一个区域再裁决
        lo = min(a_edits[i].base_start, b_edits[j].base_start)
        hi = max(a_edits[i].base_end, b_edits[j].base_end)
        i2, j2 = i + 1, j + 1
        grown = True
        while grown:
            grown = False
            while i2 < len(a_edits) and a_edits[i2].base_start < hi:
                hi = max(hi, a_edits[i2].base_end)
                i2 += 1
                grown = True
            while j2 < len(b_edits) and b_edits[j2].base_start < hi:
                hi = max(hi, b_edits[j2].base_end)
                j2 += 1
                grown = True
        grp_a = a_edits[i:i2]
        grp_b = b_edits[j:j2]
        lo = min(e.base_start for e in grp_a + grp_b)
        arep = [line for e in grp_a for line in e.repl]
        brep = [line for e in grp_b for line in e.repl]
        if not brep:
            take_clean(lo, hi, arep)
        elif not arep:
            take_clean(lo, hi, brep)
        elif arep is brep:
            take_clean(lo, hi, arep)
        else:
            hi += 1
            out.extend(base_lines[pos:lo])
            out.append("<<<<<<< a")
            out.extend(arep)
            out.append("||||||| base")
            out.extend(base_lines[lo:hi])
            out.append("=======")
            out.extend(brep)
            out.append(">>>>>>> b")
            conflicts.append(Conflict(base_lines[lo:hi], arep, brep,
                                      (lo, hi), _span(grp_a), _span(grp_b)))
            pos = hi
        i, j = i2, j2
    out.extend(base_lines[pos:])
    return MergeResult(out, conflicts)
