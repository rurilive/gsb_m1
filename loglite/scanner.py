"""扫描阶段：从清单条目里筛出可疑项。

过程日志走结构化日志层；兼容模式下消息文本（含 [scanner] 前缀）
逐行等同于原来的裸 print。
"""

from .logging import get_logger

MAX_ENTRY_SIZE = 1024 * 1024
TEMP_SUFFIXES = (".tmp", ".bak", ".swp")

log = get_logger("scanner")


def scan(entries):
    """返回可疑条目名列表：临时后缀或超出大小上限。"""
    log.info(f"[scanner] start: {len(entries)} entries")
    flagged = []
    for name, size, _mtime in entries:
        if name.endswith(TEMP_SUFFIXES):
            flagged.append(name)
            log.info(f"[scanner] flagged {name} (temp suffix)")
        elif size > MAX_ENTRY_SIZE:
            flagged.append(name)
            log.info(f"[scanner] flagged {name} (size {size} over limit)")
    ok = len(entries) - len(flagged)
    log.info(f"[scanner] done: {ok} ok, {len(flagged)} flagged")
    return flagged
