"""补丁解析、应用与反向应用。"""

import re

_HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class Hunk:
    """一个 hunk：头区间 + 体行（保留 ' '/'-'/'+' 前缀）。

    old_no_newline / new_no_newline 记录两侧的
    "\\ No newline at end of file" 标记。
    """

    __slots__ = ("old_start", "old_count", "new_start", "new_count",
                 "lines", "old_no_newline", "new_no_newline")

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
                last = cur.lines[-1][0]
                if last in (" ", "-"):
                    cur.old_no_newline = True
                if last in (" ", "+"):
                    cur.new_no_newline = True
        elif cur is not None and raw[:1] in (" ", "+", "-"):
            cur.lines.append(raw)
    return hunks


def _offset(start: int, count: int) -> int:
    """hunk 头行号（1-based）转 0-based 下标；count 为 0 时 start 指向前一行。"""
    return start - 1 if count > 0 else start


def _join(lines: list, ends_with_newline: bool) -> str:
    text = "\n".join(lines)
    if lines and ends_with_newline:
        text += "\n"
    return text


def apply_patch(text: str, patch: str) -> str:
    """按补丁逐 hunk 应用到 text，返回新文本。

    hunk 上下文与 text 不匹配时抛 ValueError，不静默跳过。
    """
    lines = text.splitlines()
    out = []
    done = 0
    ends_with_newline = text.endswith("\n")
    for hunk in parse_patch(patch):
        pos = _offset(hunk.old_start, hunk.old_count)
        old_side = [l[1:] for l in hunk.lines if l[0] in (" ", "-")]
        if lines[pos:pos + len(old_side)] != old_side:
            raise ValueError(
                f"应用失败: hunk @@ -{hunk.old_start},{hunk.old_count} "
                "上下文不匹配（补丁基线与目标版本不一致）")
        new_side = [l[1:] for l in hunk.lines if l[0] in (" ", "+")]
        out.extend(lines[done:pos])
        out.extend(new_side)
        done = pos + len(old_side)
        if done == len(lines):
            ends_with_newline = not hunk.new_no_newline
    out.extend(lines[done:])
    return _join(out, ends_with_newline)


def unapply_patch(text: str, patch: str) -> str:
    """反向应用：从打过补丁的 text 还原出基线版本。"""
    lines = text.splitlines()
    out = []
    done = 0
    ends_with_newline = text.endswith("\n")
    for hunk in parse_patch(patch):
        pos = _offset(hunk.new_start, hunk.new_count)
        expect = [l[1:] for l in hunk.lines if l[0] in (" ", "+")]
        if lines[pos:pos + len(expect)] != expect:
            raise ValueError(
                f"反向应用失败: hunk @@ -{hunk.old_start},{hunk.old_count} "
                "上下文不匹配")
        repl = [l[1:] for l in hunk.lines if l[0] in (" ", "-")]
        out.extend(lines[done:pos])
        out.extend(repl)
        done = pos + len(expect)
        if done == len(lines):
            ends_with_newline = not hunk.old_no_newline
    out.extend(lines[done:])
    return _join(out, ends_with_newline)
