"""任务表持久化：JSON 快照，保存 next_run 与 paused，供进程重启恢复。"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_UTC = timezone.utc
_LEGACY_TZ = ZoneInfo("Asia/Hong_Kong")


def _dump_trigger(trigger) -> dict:
    kind = type(trigger).__name__
    if kind == "IntervalTrigger":
        return {"kind": kind, "interval": trigger.interval.total_seconds(),
                "anchor": trigger.anchor.isoformat()}
    if kind == "DailyTrigger":
        return {"kind": kind, "hour": trigger.hour, "minute": trigger.minute,
                "tz": str(trigger.tz)}
    if kind == "MonthlyTrigger":
        return {"kind": kind, "day": trigger.day, "hour": trigger.hour,
                "minute": trigger.minute, "tz": str(trigger.tz)}
    raise TypeError(f"未知触发器类型: {kind}")


def _load_trigger(data: dict):
    from .triggers import IntervalTrigger, DailyTrigger, MonthlyTrigger
    kind = data["kind"]
    if kind == "IntervalTrigger":
        return IntervalTrigger(timedelta(seconds=data["interval"]),
                               anchor=datetime.fromisoformat(data["anchor"]))
    if kind == "DailyTrigger":
        return DailyTrigger(data["hour"], data["minute"], tz=data["tz"])
    if kind == "MonthlyTrigger":
        return MonthlyTrigger(data["day"], data["hour"], data["minute"], tz=data["tz"])
    raise TypeError(f"未知触发器类型: {kind}")


class Store:

    def save(self, path: str, tasks: dict) -> None:
        payload = []
        for task in tasks.values():
            payload.append({
                "id": task.id,
                "trigger": _dump_trigger(task.trigger),
                "next_run": task.next_run.astimezone(_UTC).isoformat(),
                "paused": task.paused,
            })
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=1))

    def load(self, path: str) -> dict:
        raw = json.loads(Path(path).read_text())
        out = {}
        from .triggers import Trigger
        from .scheduler import Task
        for item in raw:
            trigger = _load_trigger(item["trigger"])
            next_run = datetime.fromisoformat(item["next_run"])
            if next_run.tzinfo is None:
                # 兼容旧版本写出的快照：旧格式把 UTC 时刻误存成香港墙钟裸时间，
                # 这里按香港时区解读，避免老快照恢复后整体偏 8 小时。
                next_run = next_run.replace(tzinfo=_LEGACY_TZ)
            next_run = next_run.astimezone(_UTC)
            out[item["id"]] = Task(item["id"], trigger, lambda: None, next_run,
                                   paused=item.get("paused", False))
        return out
