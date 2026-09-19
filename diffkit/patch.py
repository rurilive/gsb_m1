"""补丁解析、应用与反向应用。"""

import re

_HUNK_HEAD = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class Hunk:
    """一个 hunk：头区间 + 体行（保留 ' '/'-'/'+' 前缀）。"""

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
            continue
        elif cur is not None and raw[:1] in (" ", "+", "-"):
            cur.lines.append(raw)
    return hunks


def apply_patch(text: str, patch: str) -> str:
    """按补丁逐 hunk 应用到 text，返回新文本。"""
    lines = text.splitlines()
    out = []
    done = 0
    for hunk in parse_patch(patch):
        pos = hunk.old_start
        old_side = [l[1:] for l in hunk.lines if l[0] in (" ", "-")]
        if lines[pos:pos + len(old_side)] != old_side:
            continue
        new_side = [l[1:] for l in hunk.lines if l[0] in (" ", "+")]
        out.extend(lines[done:pos])
        out.extend(new_side)
        done = pos + len(old_side)
    out.extend(lines[done:])
    return "\n".join(out)


def unapply_patch(text: str, patch: str) -> str:
    """反向应用：从打过补丁的 text 还原出基线版本。"""
    lines = text.splitlines()
    out = []
    done = 0
    for hunk in parse_patch(patch):
        pos = hunk.old_start - 1
        expect = [l[1:] for l in hunk.lines if l[0] in (" ", "+")]
        if lines[pos:pos + hunk.old_count] != expect:
            raise ValueError(
                f"反向应用失败: hunk @@ -{hunk.old_start},{hunk.old_count} 上下文不匹配")
        repl = [l[1:] for l in hunk.lines if l[0] in (" ", "-")]
        out.extend(lines[done:pos])
        out.extend(repl)
        done = pos + hunk.old_count
    out.extend(lines[done:])
    return "\n".join(out)
