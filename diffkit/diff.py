"""unified diff 生成：SequenceMatcher 行级比较，输出标准 hunk 头。"""

from difflib import SequenceMatcher

NO_NEWLINE = "\\ No newline at end of file"


def _range(start: int, count: int) -> str:
    """hunk 头里的区间串；count 为 0 时按惯例取前一行号。"""
    if count == 0:
        return f"{start - 1},0"
    if count == 1:
        return str(start)
    return f"{start},{count}"


def _group_opcodes(opcodes, n):
    """把 opcode 序列按上下文行数 n 切成 hunk 组（同 difflib 的分组逻辑）。"""
    if not opcodes:
        return
    codes = list(opcodes)
    if codes[0][0] == "equal":
        tag, i1, i2, j1, j2 = codes[0]
        codes[0] = (tag, max(i1, i2 - n), i2, max(j1, j2 - n), j2)
    if codes[-1][0] == "equal":
        tag, i1, i2, j1, j2 = codes[-1]
        codes[-1] = (tag, i1, min(i2, i1 + n), j1, min(j2, j1 + n))
    nn = n + n
    group = []
    for tag, i1, i2, j1, j2 in codes:
        if tag == "equal" and i2 - i1 > nn:
            group.append((tag, i1, min(i2, i1 + n), j1, min(j2, j1 + n)))
            yield group
            group = [(tag, max(i1, i2 - n), i2, max(j1, j2 - n), j2)]
            continue
        group.append((tag, i1, i2, j1, j2))
    if group and not (len(group) == 1 and group[0][0] == "equal"):
        yield group


def unified_diff(old_text: str, new_text: str,
                 fromfile: str = "a", tofile: str = "b", context: int = 3) -> str:
    """生成 old_text -> new_text 的 unified diff，无差异时返回空串。"""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    old_nl = old_text.endswith("\n")
    new_nl = new_text.endswith("\n")

    matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    opcodes = matcher.get_opcodes()

    # 最后一行内容相同、仅文件尾换行不同时，行级比较看不出差异，
    # 强制把最后一行改成 replace，否则换行变化会整个丢掉。
    if (old_nl != new_nl and old_lines and new_lines
            and old_lines[-1] == new_lines[-1] and opcodes):
        tag, ai1, ai2, bj1, bj2 = opcodes[-1]
        if tag == "equal":
            opcodes = opcodes[:-1]
            if ai2 - 1 > ai1:
                opcodes.append(("equal", ai1, ai2 - 1, bj1, bj2 - 1))
            opcodes.append(("replace", ai2 - 1, ai2, bj2 - 1, bj2))

    chunks = []
    for group in _group_opcodes(opcodes, context):
        i1, i2 = group[0][1], group[-1][2]
        j1, j2 = group[0][3], group[-1][4]
        header = "@@ -{} +{} @@\n".format(
            _range(i1 + 1, i2 - i1), _range(j1 + 1, j2 - j1))
        body = []
        for tag, ai1, ai2, bj1, bj2 in group:
            if tag in ("equal", "delete", "replace"):
                prefix = " " if tag == "equal" else "-"
                for k in range(ai1, ai2):
                    body.append(prefix + old_lines[k])
                    if k == len(old_lines) - 1 and not old_nl:
                        body.append(NO_NEWLINE)
            if tag in ("insert", "replace"):
                for k in range(bj1, bj2):
                    body.append("+" + new_lines[k])
                    if k == len(new_lines) - 1 and not new_nl:
                        body.append(NO_NEWLINE)
        chunks.append(header + "\n".join(body) + "\n")

    if not chunks:
        return ""
    return "--- {}\n+++ {}\n".format(fromfile, tofile) + "".join(chunks)
