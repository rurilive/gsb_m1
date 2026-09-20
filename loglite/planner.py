"""处置阶段：把问题列表编排成动作序列。

过程日志走 loglite.logging，兼容模式下文本与历史裸 print 完全一致。
"""

from .logging import get_logger

ACTION_BY_CODE = {
    "DUPLICATE": "drop-duplicate",
    "FUTURE_MTIME": "touch-back",
}

log = get_logger("planner")


def plan(problems):
    """返回动作列表 [(name, action)]，保持问题出现顺序。"""
    log.info(f"[planner] building plan: {len(problems)} problem(s)")
    actions = []
    for idx, (name, code) in enumerate(problems, start=1):
        action = ACTION_BY_CODE.get(code, "manual-review")
        actions.append((name, action))
        log.info(f"[planner] #{idx} {name} -> {action}")
    log.info(f"[planner] ready: {len(actions)} action(s)")
    return actions


def summary(actions):
    """按动作类型计数，保持首次出现顺序。"""
    counts = {}
    for _name, action in actions:
        counts[action] = counts.get(action, 0) + 1
    return counts
