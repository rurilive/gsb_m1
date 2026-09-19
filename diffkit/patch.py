"""补丁解析、应用与反向应用。"""

import re

_HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class Hunk:
    """一个 hunk：头区间 + 体行（保留 ' '/'-'/'+' 前缀）。"""

    __slots__ = ("old_start", "old_count", "new_start", "new_count", "lines",
                 "old_no_newline", "new_no_newline")

    def __init__(self, old_start, old_count, new_start, new_count):
        self.old_start = old_start
        self.old_count = old_count
        self.new_start = new_start
        self.new_count = new_count
        self.lines = []
        self.old_no_newline = False
        self.new_no_newline = False


def parse_patch(patch: str) -> list:
    """把补丁文本拆成 Hunk 列表。"""
    hunks = []
    cur = None
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            m = _HUNK_HEAD.match(raw)
            if m is None:
                raise ValueError(f"无法解析的 hunk 头: {raw}")
            cur = Hunk(
                int(m.group(1)),
                int(m.group(2)) if m.group(2) is not None else 1,
                int(m.group(3)),
                int(m.group(4)) if m.group(4) is not None else 1,
            )
            hunks.append(cur)
        elif raw.startswith("--- ") or raw.startswith("+++ "):
            cur = None
        elif raw.startswith("\\"):
            if cur is not None and cur.lines:
                prev = cur.lines[-1][0]
                if prev in (" ", "-"):
                    cur.old_no_newline = True
                if prev in (" ", "+"):
                    cur.new_no_newline = True
        elif cur is not None and raw[:1] in (" ", "+", "-"):
            cur.lines.append(raw)
    return hunks


def _hunk_pos(start: int, count: int) -> int:
    """hunk 头是 1 基行号；count 为 0 时表示在该行之后插入。"""
    return start if count == 0 else start - 1


def apply_patch(text: str, patch: str) -> str:
    """按补丁逐 hunk 应用到 text，返回新文本；上下文不匹配时抛 ValueError。"""
    lines = text.splitlines()
    out = []
    done = 0
    ends_with_nl = text.endswith("\n")
    for hunk in parse_patch(patch):
        pos = _hunk_pos(hunk.old_start, hunk.old_count)
        old_side = [l[1:] for l in hunk.lines if l[0] in (" ", "-")]
        if lines[pos:pos + len(old_side)] != old_side:
            raise ValueError(
                f"补丁应用失败: hunk @@ -{hunk.old_start},{hunk.old_count} "
                f"与目标文件内容不匹配")
        new_side = [l[1:] for l in hunk.lines if l[0] in (" ", "+")]
        out.extend(lines[done:pos])
        out.extend(new_side)
        done = pos + len(old_side)
        if done == len(lines):
            ends_with_nl = not hunk.new_no_newline
    out.extend(lines[done:])
    if not out:
        return ""
    return "\n".join(out) + ("\n" if ends_with_nl else "")


def unapply_patch(text: str, patch: str) -> str:
    """反向应用：从打过补丁的 text 还原出基线版本。"""
    lines = text.splitlines()
    out = []
    done = 0
    ends_with_nl = text.endswith("\n")
    for hunk in parse_patch(patch):
        pos = _hunk_pos(hunk.new_start, hunk.new_count)
        expect = [l[1:] for l in hunk.lines if l[0] in (" ", "+")]
        if lines[pos:pos + len(expect)] != expect:
            raise ValueError(
                f"反向应用失败: hunk @@ +{hunk.new_start},{hunk.new_count} 上下文不匹配")
        repl = [l[1:] for l in hunk.lines if l[0] in (" ", "-")]
        out.extend(lines[done:pos])
        out.extend(repl)
        done = pos + len(expect)
        if done == len(lines):
            ends_with_nl = not hunk.old_no_newline
    out.extend(lines[done:])
    if not out:
        return ""
    return "\n".join(out) + ("\n" if ends_with_nl else "")
