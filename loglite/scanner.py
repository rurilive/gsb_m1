"""扫描阶段：从清单条目里筛出可疑项。

过程日志目前是裸 print，前缀格式是本模块自己定的。
"""

MAX_ENTRY_SIZE = 1024 * 1024
TEMP_SUFFIXES = (".tmp", ".bak", ".swp")


def scan(entries):
    """返回可疑条目名列表：临时后缀或超出大小上限。"""
    print(f"[scanner] start: {len(entries)} entries")
    flagged = []
    for name, size, _mtime in entries:
        if name.endswith(TEMP_SUFFIXES):
            flagged.append(name)
            print(f"[scanner] flagged {name} (temp suffix)")
        elif size > MAX_ENTRY_SIZE:
            flagged.append(name)
            print(f"[scanner] flagged {name} (size {size} over limit)")
    ok = len(entries) - len(flagged)
    print(f"[scanner] done: {ok} ok, {len(flagged)} flagged")
    return flagged
