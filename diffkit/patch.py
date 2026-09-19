"""补丁解析、应用与反向应用。"""

import re

_HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class Hunk:
    """一个 hunk：头区间 + 体行（保留 ' '/'-'/'+' 前缀）。

    no_newline: 若 hunk 内含 `\\ No newline at end of file` 标记，
    记录标记前一行体行的前缀（' '/'-'/'+'），否则为 None。
    """

    __slots__ = ("old_start", "old_count", "new_start", "new_count",
                 "lines", "no_newline")

    def __init__(self, old_start, old_count, new_start, new_count):
        self.old_start = old_start
        self.old_count = old_count
        self.new_start = new_start
        self.new_count = new_count
        self.lines = []
        self.no_newline = None


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
                cur.no_newline = cur.lines[-1][0]
        elif cur is not None and raw[:1] in (" ", "+", "-"):
            cur.lines.append(raw)
    return hunks


def _hunk_pos(start: int, count: int) -> int:
    """hunk 头行号（1 基）转 0 基下标；count 为 0 时行号指向前一行。"""
    return start - 1 if count else start


def _join(out: list, trailing_nl: bool) -> str:
    result = "\n".join(out)
    if trailing_nl and out:
        result += "\n"
    return result


def apply_patch(text: str, patch: str) -> str:
    """按补丁逐 hunk 应用到 text，返回新文本。上下文不匹配时抛 ValueError。"""
    lines = text.splitlines()
    hunks = parse_patch(patch)
    out = []
    done = 0
    for hunk in hunks:
        pos = _hunk_pos(hunk.old_start, hunk.old_count)
        old_side = [l[1:] for l in hunk.lines if l[0] in (" ", "-")]
        if lines[pos:pos + len(old_side)] != old_side:
            raise ValueError(
                f"应用失败: hunk @@ -{hunk.old_start},{hunk.old_count} 上下文不匹配")
        new_side = [l[1:] for l in hunk.lines if l[0] in (" ", "+")]
        out.extend(lines[done:pos])
        out.extend(new_side)
        done = pos + len(old_side)
    out.extend(lines[done:])
    trailing_nl = text.endswith("\n")
    if hunks and done == len(lines):
        # 末尾 hunk 覆盖到文件尾：结尾换行由补丁决定。
        # 标记在 '-' 后表示旧文件无尾换行（新文件有）；在 '+'/' ' 后表示新文件无。
        trailing_nl = hunks[-1].no_newline in (None, "-")
    return _join(out, trailing_nl)


def unapply_patch(text: str, patch: str) -> str:
    """反向应用：从打过补丁的 text 还原出基线版本。"""
    lines = text.splitlines()
    hunks = parse_patch(patch)
    out = []
    done = 0
    for hunk in hunks:
        pos = _hunk_pos(hunk.new_start, hunk.new_count)
        expect = [l[1:] for l in hunk.lines if l[0] in (" ", "+")]
        if lines[pos:pos + len(expect)] != expect:
            raise ValueError(
                f"反向应用失败: hunk @@ -{hunk.old_start},{hunk.old_count} 上下文不匹配")
        repl = [l[1:] for l in hunk.lines if l[0] in (" ", "-")]
        out.extend(lines[done:pos])
        out.extend(repl)
        done = pos + len(expect)
    out.extend(lines[done:])
    trailing_nl = text.endswith("\n")
    if hunks and done == len(lines):
        # 标记在 '+' 后表示新文件无尾换行（旧文件有）；在 '-'/' ' 后表示旧文件无。
        trailing_nl = hunks[-1].no_newline in (None, "+")
    return _join(out, trailing_nl)
