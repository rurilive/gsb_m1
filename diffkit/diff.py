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


def _newline_only_diff(old_lines, old_nl, new_nl,
                       fromfile, tofile, context):
    """内容相同、仅末行换行状态不同的 diff（SequenceMatcher 看不出这种差异）。"""
    n = len(old_lines)
    i1 = max(0, n - 1 - context)
    header = "@@ -{} +{} @@\n".format(
        _range(i1 + 1, n - i1), _range(i1 + 1, n - i1))
    body = [" " + old_lines[k] for k in range(i1, n - 1)]
    body.append("-" + old_lines[-1])
    if not old_nl:
        body.append(NO_NEWLINE)
    body.append("+" + old_lines[-1])
    if not new_nl:
        body.append(NO_NEWLINE)
    return ("--- {}\n+++ {}\n".format(fromfile, tofile)
            + header + "\n".join(body) + "\n")


def unified_diff(old_text: str, new_text: str,
                 fromfile: str = "a", tofile: str = "b", context: int = 3) -> str:
    """生成 old_text -> new_text 的 unified diff，无差异时返回空串。"""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    old_nl = old_text.endswith("\n")
    new_nl = new_text.endswith("\n")

    if old_lines == new_lines:
        if old_nl == new_nl or not old_lines:
            return ""
        return _newline_only_diff(old_lines, old_nl, new_nl,
                                  fromfile, tofile, context)

    matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    chunks = []
    last_i2 = last_j2 = 0
    for group in matcher.get_grouped_opcodes(context):
        i1, i2 = group[0][1], group[-1][2]
        j1, j2 = group[0][3], group[-1][4]
        last_i2, last_j2 = i2, j2
        header = "@@ -{} +{} @@\n".format(
            _range(i1 + 1, i2 - i1), _range(j1 + 1, j2 - j1))
        body = []
        for tag, ai1, ai2, bj1, bj2 in group:
            if tag == "equal":
                # 末行换行状态不同时，最后一行要按替换输出，
                # 否则 \\ No newline 标记无法区分属于哪一侧。
                split_tail = (ai2 == len(old_lines) and old_nl != new_nl)
                end = ai2 - 1 if split_tail else ai2
                for k in range(ai1, end):
                    body.append(" " + old_lines[k])
                    # 上下文行可能恰好是某一侧的末行，两侧都要检查
                    if (k == len(old_lines) - 1 and not old_nl) or \
                            (k + (bj1 - ai1) == len(new_lines) - 1
                             and not new_nl):
                        body.append(NO_NEWLINE)
                if split_tail:
                    body.append("-" + old_lines[ai2 - 1])
                    if not old_nl:
                        body.append(NO_NEWLINE)
                    body.append("+" + new_lines[bj2 - 1])
                    if not new_nl:
                        body.append(NO_NEWLINE)
            elif tag == "replace":
                for k in range(ai1, ai2):
                    body.append("-" + old_lines[k])
                    if k == len(old_lines) - 1 and not old_nl:
                        body.append(NO_NEWLINE)
                for k in range(bj1, bj2):
                    body.append("+" + new_lines[k])
                    if k == len(new_lines) - 1 and not new_nl:
                        body.append(NO_NEWLINE)
            elif tag == "delete":
                for k in range(ai1, ai2):
                    body.append("-" + old_lines[k])
                    if k == len(old_lines) - 1 and not old_nl:
                        body.append(NO_NEWLINE)
            elif tag == "insert":
                for k in range(bj1, bj2):
                    body.append("+" + new_lines[k])
                    if k == len(new_lines) - 1 and not new_nl:
                        body.append(NO_NEWLINE)
        chunks.append(header + "\n".join(body) + "\n")

    # 内容改动都在文件中部时，末尾的“仅换行符差异”会落在所有 hunk
    # 之外（末尾相同行被 context 截断），需要单独补一个 hunk 记录它。
    if old_nl != new_nl and old_lines and new_lines \
            and last_i2 < len(old_lines):
        tail = len(old_lines) - last_i2  # 末尾相同行数（== len(new_lines) - last_j2）
        k = min(context + 1, tail)
        o_start = len(old_lines) - k
        n_start = len(new_lines) - k
        header = "@@ -{} +{} @@\n".format(
            _range(o_start + 1, k), _range(n_start + 1, k))
        body = [" " + old_lines[o_start + t] for t in range(k - 1)]
        body.append("-" + old_lines[-1])
        if not old_nl:
            body.append(NO_NEWLINE)
        body.append("+" + new_lines[-1])
        if not new_nl:
            body.append(NO_NEWLINE)
        chunks.append(header + "\n".join(body) + "\n")

    if not chunks:
        return ""
    return "--- {}\n+++ {}\n".format(fromfile, tofile) + "".join(chunks)
