"""罐子的 JSON 导入导出（网关重启恢复用）。"""

import json
from datetime import datetime
from pathlib import Path

from .cookie import Cookie


def dump(jar, path) -> None:
    payload = [_to_dict(c) for c in jar.snapshot()]
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def load(jar, path) -> None:
    for item in json.loads(Path(path).read_text(encoding="utf-8")):
        jar.add(_from_dict(item))


def _to_dict(c: Cookie) -> dict:
    return {
        "name": c.name,
        "value": c.value,
        "domain": c.domain,
        "path": c.path,
        "expires": c.expires.isoformat() if c.expires else None,
    }


def _from_dict(item: dict) -> Cookie:
    return Cookie(
        name=item["name"],
        value=item["value"],
        domain=item["domain"],
        path=item.get("path", "/"),
        expires=datetime.fromisoformat(item["expires"]) if item["expires"] else None,
    )
