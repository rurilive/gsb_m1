"""补丁解析、应用与反向应用。"""

import re

_HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class Hunk:
    """一个 hunk：头区间 + 体行（保留 ' '/'-'/'+' 前缀，'\\' 标记行原样保留）。"""

    __slots__ = ("old_start", "old_count", "new_start", "new_count", "lines")

    def __init__(self, old_start, old_count, new_start, new_count):
        self.old_start = old_start
        self.old_count = old_count
        self.new_start = new_start
        self.new_count = new_count
        self.lines = []


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
            if cur is not None:
                cur.lines.append(raw)
        elif cur is not None and raw[:1] in (" ", "+", "-"):
            cur.lines.append(raw)
    return hunks


def _offset(start: int, count: int) -> int:
    """hunk 头的 1 基行号转 0 基下标；count 为 0 时 start 是插入点前的行号。"""
    return start - 1 if count > 0 else start


def _side_lines(hunk: Hunk, prefixes: tuple) -> list:
    return [l[1:] for l in hunk.lines if l[0] in prefixes]


def _no_nl_at_end(hunk: Hunk, prefixes: tuple) -> bool:
    """该侧最后一行后面是否紧跟 \\ No newline 标记（标记只注解紧邻的上一行）。"""
    last = None
    for idx, raw in enumerate(hunk.lines):
        if raw[0] in prefixes:
            last = idx
    if last is None or last + 1 >= len(hunk.lines):
        return False
    return hunk.lines[last + 1].startswith("\\")


def apply_patch(text: str, patch: str) -> str:
    """按补丁逐 hunk 应用到 text，返回新文本。上下文不匹配时抛 ValueError。"""
    lines = text.splitlines()
    out = []
    done = 0
    ends_nl = text.endswith("\n")
    for hunk in parse_patch(patch):
        pos = _offset(hunk.old_start, hunk.old_count)
        old_side = _side_lines(hunk, (" ", "-"))
        if lines[pos:pos + len(old_side)] != old_side:
            raise ValueError(
                f"补丁应用失败: hunk @@ -{hunk.old_start},{hunk.old_count} "
                f"与目标文件内容不匹配")
        new_side = _side_lines(hunk, (" ", "+"))
        out.extend(lines[done:pos])
        out.extend(new_side)
        done = pos + len(old_side)
        if done == len(lines):
            ends_nl = not _no_nl_at_end(hunk, (" ", "+"))
    out.extend(lines[done:])
    if not out:
        return ""
    return "\n".join(out) + ("\n" if ends_nl else "")


def unapply_patch(text: str, patch: str) -> str:
    """反向应用：从打过补丁的 text 还原出基线版本。"""
    lines = text.splitlines()
    out = []
    done = 0
    ends_nl = text.endswith("\n")
    for hunk in parse_patch(patch):
        pos = _offset(hunk.new_start, hunk.new_count)
        expect = _side_lines(hunk, (" ", "+"))
        if lines[pos:pos + len(expect)] != expect:
            raise ValueError(
                f"反向应用失败: hunk @@ -{hunk.old_start},{hunk.old_count} "
                f"上下文不匹配")
        repl = _side_lines(hunk, (" ", "-"))
        out.extend(lines[done:pos])
        out.extend(repl)
        done = pos + len(expect)
        if done == len(lines):
            ends_nl = not _no_nl_at_end(hunk, (" ", "-"))
    out.extend(lines[done:])
    if not out:
        return ""
    return "\n".join(out) + ("\n" if ends_nl else "")
