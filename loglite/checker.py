"""核查阶段：重复条目与异常 mtime。

过程日志走结构化日志层；兼容模式下消息文本（含 ==> checker: 前缀）
逐行等同于原来的裸 print。
"""

import time

from .logging import get_logger

FUTURE_MARGIN = 60  # mtime 超出当前时间 60s 视为异常

log = get_logger("checker")


def check(entries, now=None):
    """返回问题列表 [(name, code)]，code 为 DUPLICATE / FUTURE_MTIME。

    now 可注入，便于测试固定时间基准。
    """
    if now is None:
        now = time.time()
    log.info(f"==> checker: begin over {len(entries)} entries")
    problems = []
    seen = set()
    for name, _size, _mtime in entries:
        if name in seen:
            problems.append((name, "DUPLICATE"))
            log.info(f"==> checker: duplicate entry {name}")
        seen.add(name)
    for name, _size, mtime in entries:
        if mtime > now + FUTURE_MARGIN:
            problems.append((name, "FUTURE_MTIME"))
            log.info(f"==> checker: mtime in future: {name}")
    log.info(f"==> checker: found {len(problems)} problem(s)")
    return problems
