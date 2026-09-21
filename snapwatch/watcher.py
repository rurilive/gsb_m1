"""Watcher：轮询扫描，比对前后两份快照，把差异变成事件。

语义和 snapwatch.reference 的对拍基准一致：

- 对同一路径只看相对上一次已发布状态的净效果，一轮内出现又消失不报；
- 变化要静默 debounce 秒之后才发布，静默期里又变了重新计时；
- 同一个 inode 旧路径消失、新路径出现且两边本轮都要发布时，配成 moved，
  新路径原本已存在则按 modified；
- 批内顺序为 deleted（深的在前）、modified、moved、created（浅的在前）。

有些文件系统的 mtime 只到秒（甚至更粗），同一时间片里连写两笔且长度
相同，元数据完全分不出来。这类文件在最近一个 granularity 秒的时间窗内
惰性校验一次内容，静止后不再重读；内容未变则静默采用，不误报。
读不出来的目录沿用上一轮的子树，避免权限瞬断时整棵子树被误报删除。
"""

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

    def __init__(self, root, fs=None, clock=time.time, interval=0.5,
                 debounce=0.25, granularity=1.0):
        self.fs = fs if fs is not None else SysFS()
        self.root = os.path.abspath(root)
        self.clock = clock
        self.interval = interval
        self.debounce = float(debounce)
        # mtime 的时间片宽度（秒），只有最近这个时间窗里改过的文件才
        # 可能需要读内容来分辨同时间片、同长度的连写
        self.granularity_ns = int(float(granularity) * 1e9)
        self.last_poll_at = None
        self._scanner = PollScanner(self.fs, self.root)
        self._snapshot = self._scanner.scan()
        self._callbacks, self._thread = [], None
        self._stopped = threading.Event()
        now = self.clock()
        # 已发布状态、最近观察到的状态、待确认变化：
        # 状态五元组 (is_dir, size, mtime_ns, inode, digest)，digest
        # 未知时是 None
        self._committed, self._observed, self._pending = {}, {}, {}
        # inode -> (mtime_ns, digest)：该元数据下内容已经确认过的缓存
        self._known = {}
        # inode -> 第一次见到它时的 mtime_ns。粗时间戳盘上同 inode 可能
        # 顶着旧 mtime 被连写，首次见到的那个 mtime 下内容不可缓存，要等
        # 它后来拿到更新的 mtime
        self._first_seen = {}
        for path, entry in self._snapshot.entries.items():
            if entry.is_dir:
                state = (True, entry.size, entry.mtime_ns, entry.inode, None)
            else:
                state = (False, entry.size, entry.mtime_ns, entry.inode, None)
                # 比一个完整时间片还旧的文件，不可能藏着同时间片连写，
                # 打底时不读内容
                if now * 1e9 - entry.mtime_ns >= self.granularity_ns:
                    self._known[entry.inode] = (entry.mtime_ns, None)
            self._committed[path] = state
            self._observed[path] = state

    def snapshot(self):
        """最近一次扫描的快照。"""
        return self._snapshot

    def subscribe(self, callback):
        """挂一个回调，事件按批内顺序逐个喂进去。"""
        self._callbacks.append(callback)

    def poll(self):
        """再扫一遍，返回这批事件，同时喂给回调。"""
        now = self.clock()
        self.last_poll_at = now
        fresh = self._scanner.scan()
        retained = self._retain_inaccessible(fresh)
        self._refresh_states(fresh, now, retained)
        self._snapshot = fresh
        events = self._feed(now, fresh)
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

    def _retain_inaccessible(self, fresh):
        """读不出来的目录把上一轮整棵子树原样保留，当成本轮没动过。"""
        if not fresh.incomplete:
            return frozenset()
        prefixes = tuple(sorted(fresh.incomplete))
        retained = set()
        for path, entry in self._snapshot.entries.items():
            if path in fresh.entries:
                continue
            parent = path.rsplit("/", 1)[0] if "/" in path else ""
            if any(prefix == "" or parent == prefix
                   or parent.startswith(prefix + "/")
                   for prefix in prefixes):
                fresh.entries[path] = entry
                entry._state = self._observed[path]
                retained.add(path)
        return frozenset(retained)

    def _refresh_states(self, fresh, now, skip=()):
        """给本轮快照补出每个节点的状态五元组，必要时惰性读内容。"""
        now_ns = now * 1e9
        for path, entry in fresh.entries.items():
            if path in skip:
                continue
            if entry.is_dir:
                entry._state = (
                    True, entry.size, entry.mtime_ns, entry.inode, None)
                continue
            observed = self._observed.get(path)
            same_meta = (
                observed is not None and not observed[0]
                and (observed[1], observed[2], observed[3])
                == (entry.size, entry.mtime_ns, entry.inode))
            known = self._known.get(entry.inode)
            first_mtime = self._first_seen.get(entry.inode)
            if first_mtime is None:
                self._first_seen[entry.inode] = entry.mtime_ns
                first_mtime = entry.mtime_ns
            if known is not None and known[0] == entry.mtime_ns:
                # 改名换路径后 inode + mtime 相同，内容缓存还能用
                digest = known[1]
            elif (same_meta and observed[4] is not None
                  and entry.mtime_ns > first_mtime
                  and now_ns - entry.mtime_ns >= self.granularity_ns):
                # 上轮读过、此刻已熬过完整时间片：之后的写入必然拿到新
                # mtime，上轮内容就是最终内容，收入缓存后不再读盘
                digest = observed[4]
                self._known[entry.inode] = (entry.mtime_ns, digest)
            else:
                # 元数据变了，或者元数据没变但还处在可能发生同时间片
                # 连写的窗口里：读一次把净效果看全。熬过完整时间片之后
                # 才缓存，之后任何写入按时间片取整必然拿到新 mtime
                digest = self._digest(entry)
                # 只有拿到比首次见面时更新的 mtime、且熬过完整时间片才
                # 能缓存：首次见面的那个 mtime 可能被同时间片连写复用
                if (digest is not None
                        and entry.mtime_ns > first_mtime
                        and now_ns - entry.mtime_ns >= self.granularity_ns):
                    self._known[entry.inode] = (entry.mtime_ns, digest)
            entry._state = (
                False, entry.size, entry.mtime_ns, entry.inode, digest)
            entry._same_meta = same_meta
        live_inodes = {entry.inode for entry in fresh.entries.values()}
        for table in (self._known, self._first_seen):
            for dead in tuple(table):
                if dead not in live_inodes:
                    del table[dead]

    @staticmethod
    def _digest(entry):
        try:
            return entry.digest
        except OSError:
            # 内容暂时读不出来（正在被替换等瞬态），本轮按未知处理，
            # 下一轮再确认
            return None

    def _feed(self, now, fresh):
        """按净效果 + debounce 收本批事件，语义对齐 OpReference.feed。"""
        for path in set(self._observed) | set(fresh.entries):
            entry = fresh.entries.get(path)
            state = entry._state if entry is not None else None
            if state == self._observed.get(path):
                continue
            committed = self._committed.get(path)
            if (state is not None and committed is not None
                    and committed[4] is None and state[4] is not None
                    and state[:4] == committed[:4]):
                # 打底快照只读元数据、没碰内容；第一次确认内容时元数据
                # 没变就把 digest 静默收进基准，不当成一次修改
                self._committed[path] = state
                self._observed[path] = state
                self._pending.pop(path, None)
                continue
            self._observed[path] = state
            if state == self._committed.get(path):
                self._pending.pop(path, None)
            else:
                # 从本轮扫描时刻起静默计时（和 OpReference.feed(now,...)
                # 同一个锚点）；静默期里状态再变，下轮会重新计时
                self._pending[path] = (now, state)
        ready = [(path, state) for path, (at, state) in self._pending.items()
                 if now - at >= self.debounce]
        if not ready:
            return []
        pairs = []
        for path, state in ready:
            del self._pending[path]
            pairs.append((path, self._committed.pop(path, None), state))
            if state is None:
                self._observed.pop(path, None)
            else:
                self._committed[path] = state
        from .reference import publish
        return publish(pairs)
