"""目录快照，以及两份快照之间的差分。"""

import json
import os
from dataclasses import dataclass

from snapwire.hashing import hash_file

SNAPSHOT_VERSION = 1


@dataclass(frozen=True)
class Entry:
    """快照里的一条文件记录。"""

    size: int
    digest: str


@dataclass(frozen=True)
class Change:
    """一条差异，kind 取 added、removed、modified。"""

    kind: str
    path: str


class Snapshot:
    """某目录在某一刻的文件清单，路径统一用斜杠分隔、相对 root。"""

    def __init__(self, root, entries):
        self.root = root
        self.entries = dict(entries)

    def paths(self):
        """排好序的相对路径列表。"""
        return sorted(self.entries)

    def __len__(self):
        return len(self.entries)

    def __contains__(self, path):
        return path in self.entries

    def __eq__(self, other):
        if not isinstance(other, Snapshot):
            return NotImplemented
        return self.entries == other.entries

    def __repr__(self):
        return "Snapshot(root=%r, entries=%d)" % (self.root, len(self.entries))


def take_snapshot(root):
    """遍历 root 下所有文件建快照。

    名字以点开头的文件与目录一律跳过，路径按 / 拼接，
    这样同一份目录在任何平台上得到同一份清单。
    """
    entries = {}
    for base, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            entries[rel] = Entry(size=os.path.getsize(full), digest=hash_file(full))
    return Snapshot(root, entries)


def compare_snapshots(old, new):
    """列出 old 到 new 的差异，按路径升序。

    同名同内容不算差异，哪怕写入时间变过。
    """
    changes = []
    for path in sorted(set(old.entries) | set(new.entries)):
        before = old.entries.get(path)
        after = new.entries.get(path)
        if before is None:
            changes.append(Change("added", path))
        elif after is None:
            changes.append(Change("removed", path))
        elif before != after:
            changes.append(Change("modified", path))
    return changes


def save_snapshot(snapshot, path):
    """把快照写成 JSON 文件，父目录不存在就建出来。"""
    payload = {
        "version": SNAPSHOT_VERSION,
        "root": snapshot.root,
        "entries": {
            p: {"size": e.size, "digest": e.digest}
            for p, e in sorted(snapshot.entries.items())
        },
    }
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, indent=2)


def load_snapshot(path):
    """读回快照文件，版本对不上抛 ValueError。"""
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if payload.get("version") != SNAPSHOT_VERSION:
        raise ValueError(
            "unsupported snapshot version: %r" % payload.get("version"))
    entries = {
        p: Entry(size=e["size"], digest=e["digest"])
        for p, e in payload["entries"].items()
    }
    return Snapshot(payload["root"], entries)
