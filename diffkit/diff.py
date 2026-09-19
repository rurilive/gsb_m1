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


def unified_diff(old_text: str, new_text: str,
                 fromfile: str = "a", tofile: str = "b", context: int = 3) -> str:
    """生成 old_text -> new_text 的 unified diff，无差异时返回空串。"""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    old_nl = old_text.endswith("\n")
    new_nl = new_text.endswith("\n")

    matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    chunks = []
    for group in matcher.get_grouped_opcodes(context):
        i1, i2 = group[0][1], group[-1][2]
        j1, j2 = group[0][3], group[-1][4]
        header = "@@ -{} +{} @@\n".format(
            _range(i1 + 1, i2 - i1), _range(j1 + 1, j2 - j1))
        body = []
        for tag, ai1, ai2, bj1, bj2 in group:
            if tag == "equal":
                for line in old_lines[ai1:ai2]:
                    body.append(" " + line)
            elif tag == "replace":
                for line in old_lines[ai1:ai2]:
                    body.append("-" + line)
                for line in new_lines[bj1:bj2]:
                    body.append("+" + line)
            elif tag == "delete":
                for line in old_lines[ai1:ai2]:
                    body.append("-" + line)
            elif tag == "insert":
                for line in new_lines[bj1:bj2]:
                    body.append("+" + line)
        if old_lines and i2 == len(old_lines) and not old_nl:
            body.append(NO_NEWLINE)
        if new_lines and j2 == len(new_lines) and not new_nl:
            body.append(NO_NEWLINE)
        chunks.append(header + "\n".join(body) + "\n")

    if not chunks:
        return ""
    return "--- {}\n+++ {}\n".format(fromfile, tofile) + "".join(chunks)
