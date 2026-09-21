"""Watcher：轮询扫描，比对前后两份快照，把差异变成事件。"""

import os
import threading
import time

from .fs import SysFS
from .scanner import PollScanner

CREATED = "created"
MODIFIED = "modified"
DELETED = "deleted"
MOVED = "moved"


class Event:
    """一条变化事件。moved 的 path 是旧路径，dest 是新路径。"""

    __slots__ = ("kind", "path", "dest", "is_dir")

    def __init__(self, kind, path, is_dir=False, dest=None):
        self.kind = kind
        self.path = path
        self.is_dir = is_dir
        self.dest = dest

    def __eq__(self, other):
        return (self.kind, self.path, self.dest, self.is_dir) == (
            other.kind, other.path, other.dest, other.is_dir)

    def __hash__(self):
        return hash((self.kind, self.path, self.dest, self.is_dir))

    def __repr__(self):
        if self.kind == MOVED:
            return "Event(moved %r -> %r)" % (self.path, self.dest)
        return "Event(%s %r)" % (self.kind, self.path)


class Watcher:
    """盯住一棵目录树，poll() 取一批事件，subscribe() 挂回调。"""

    def __init__(self, root, fs=None, clock=time.time, interval=0.5):
        self.fs = fs if fs is not None else SysFS()
        self.root = os.path.abspath(root)
        self.clock = clock
        self.interval = interval
        self.last_poll_at = None
        self._scanner = PollScanner(self.fs, self.root)
        self._snapshot = self._scanner.scan()
        self._callbacks, self._thread = [], None
        self._stopped = threading.Event()

    def snapshot(self):
        """最近一次扫描的快照。"""
        return self._snapshot

    def subscribe(self, callback):
        """挂一个回调，事件按批内顺序逐个喂进去。"""
        self._callbacks.append(callback)

    def poll(self):
        """再扫一遍，返回这批事件，同时喂给回调。"""
        self.last_poll_at = self.clock()
        fresh = self._scanner.scan()
        events = self._diff(self._snapshot, fresh)
        self._snapshot = fresh
        for event in events:
            for callback in self._callbacks:
                callback(event)
        return events

    def start(self):
        """起一个后台线程按 interval 反复 poll。"""
        if self._thread is not None:
            return
        self._stopped.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停掉后台线程，可以重复调。"""
        self._stopped.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=self.interval + 1.0)

    def _loop(self):
        while not self._stopped.is_set():
            self.poll()
            self._stopped.wait(self.interval)

    def _diff(self, prev, now):
        events = []
        now_inodes = {e.inode: p for p, e in now.entries.items()}
        for path in sorted(now.entries):
            fresh = now.entries[path]
            old = prev.entries.get(path)
            if old is None:
                events.append(Event(CREATED, path, fresh.is_dir))
            elif old.inode != fresh.inode:
                # 路径还在但 inode 换了，按旧文件没了、新文件来了记
                events.append(Event(DELETED, path, old.is_dir))
                events.append(Event(CREATED, path, fresh.is_dir))
            elif (old.mtime_ns, old.size) != (fresh.mtime_ns, fresh.size):
                events.append(Event(MODIFIED, path, fresh.is_dir))
        for path in sorted(prev.entries):
            old = prev.entries[path]
            if path in now.entries:
                continue
            dest = now_inodes.get(old.inode)
            if dest is not None and dest != path:
                events.append(Event(MOVED, path, old.is_dir, dest))
            else:
                events.append(Event(DELETED, path, old.is_dir))
        return events
