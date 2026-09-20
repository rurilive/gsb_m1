"""核查阶段：重复条目与异常 mtime。

过程日志是裸 print，格式与 scanner 各写各的。
"""

import time

FUTURE_MARGIN = 60  # mtime 超出当前时间 60s 视为异常


def check(entries, now=None):
    """返回问题列表 [(name, code)]，code 为 DUPLICATE / FUTURE_MTIME。

    now 可注入，便于测试固定时间基准。
    """
    if now is None:
        now = time.time()
    print(f"==> checker: begin over {len(entries)} entries")
    problems = []
    seen = set()
    for name, _size, _mtime in entries:
        if name in seen:
            problems.append((name, "DUPLICATE"))
            print(f"==> checker: duplicate entry {name}")
        seen.add(name)
    for name, _size, mtime in entries:
        if mtime > now + FUTURE_MARGIN:
            problems.append((name, "FUTURE_MTIME"))
            print(f"==> checker: mtime in future: {name}")
    print(f"==> checker: found {len(problems)} problem(s)")
    return problems
