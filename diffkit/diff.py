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


def _emit(body: list, prefix: str, line: str) -> None:
    """输出一行 hunk 体；行尾无换行（即文件最后一行）时紧随其后补标记。"""
    if line.endswith("\n"):
        body.append(prefix + line[:-1])
    else:
        body.append(prefix + line)
        body.append(NO_NEWLINE)


def unified_diff(old_text: str, new_text: str,
                 fromfile: str = "a", tofile: str = "b", context: int = 3) -> str:
    """生成 old_text -> new_text 的 unified diff，无差异时返回空串。"""
    # keepends=True：让"仅文件尾换行不同"也体现为最后一行的 replace，
    # 同时保证 NO_NEWLINE 标记只可能出现在文件最后一行上。
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

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
                    _emit(body, " ", line)
            elif tag == "replace":
                for line in old_lines[ai1:ai2]:
                    _emit(body, "-", line)
                for line in new_lines[bj1:bj2]:
                    _emit(body, "+", line)
            elif tag == "delete":
                for line in old_lines[ai1:ai2]:
                    _emit(body, "-", line)
            elif tag == "insert":
                for line in new_lines[bj1:bj2]:
                    _emit(body, "+", line)
        chunks.append(header + "\n".join(body) + "\n")

    if not chunks:
        return ""
    return "--- {}\n+++ {}\n".format(fromfile, tofile) + "".join(chunks)
