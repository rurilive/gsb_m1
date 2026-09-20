"""操作日志与对拍基准。

OpScript 在真实目录上按虚拟时钟做随机操作，把每一步之后的可观测状态记进
操作日志；OpReference 只看这份日志，算出一次 poll 该发布出哪些事件。状态是
五元组 (is_dir, size, mtime_ns, inode, digest)，路径不在时是 None。

对拍语义，Watcher.poll 必须和它对上：同一路径的变化合并成净效果，一轮里出现
又消失的路径不报；变化要静默 debounce 秒之后才发布，静默期里又变了就从最后
一次算起；同一个 inode 从旧路径消失、在新路径出现，两条又都在本轮发布、且新
路径原本不存在时，配成一条 moved，两条路径都不再单独出事件，新路径原本就在
时按 modified 算；一批事件的顺序是删除（深的在前，子先于父）、modified、
moved、created（浅的在前，父先于子），同类里按路径排。
"""

import hashlib
import os
import random
import stat as stat_module

from .watcher import CREATED, DELETED, MODIFIED, MOVED, Event

_RANK = {DELETED: 0, MODIFIED: 1, MOVED: 2, CREATED: 3}


def state_of(path):
    """路径当前的可观测状态，不存在时返回 None。"""
    try:
        info = os.stat(path)
    except OSError:
        return None
    if stat_module.S_ISDIR(info.st_mode):
        return (True, info.st_size, info.st_mtime_ns, info.st_ino, None)
    with open(path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return (False, info.st_size, info.st_mtime_ns, info.st_ino, digest)


def sort_key(event):
    """批内事件的顺序：删除、修改、移动、创建，删除深的在前，创建浅的在前。"""
    depth = event.path.count("/") + 1
    if event.kind == DELETED:
        depth = -depth
    return (_RANK[event.kind], depth, event.path)


def publish(pairs):
    """把 (路径, 旧状态, 新状态) 收成一批排好序的事件。"""
    events, created_at, deleted_at = [], {}, {}
    for path, old, new in pairs:
        if old is None:
            created_at[new[3]] = len(events)
            events.append(Event(CREATED, path, new[0]))
        elif new is None:
            deleted_at[old[3]] = len(events)
            events.append(Event(DELETED, path, old[0]))
        elif old != new:
            events.append(Event(MODIFIED, path, new[0]))
    dropped = set()
    for inode, index in deleted_at.items():
        mate = created_at.get(inode)
        if mate is not None and mate not in dropped:
            events[index] = Event(MOVED, events[index].path,
                                  events[index].is_dir, events[mate].path)
            dropped.add(mate)
    events = [event for index, event in enumerate(events)
              if index not in dropped]
    events.sort(key=sort_key)
    return events


class OpReference:
    """只看操作日志的对拍基准。"""

    def __init__(self, debounce=0.25):
        self.debounce = float(debounce)
        self._committed, self._observed, self._pending = {}, {}, {}

    def prime(self, states):
        """打底：把存量树的状态当作已经发布过的东西。"""
        self._committed = dict(states)
        self._observed = dict(states)

    def feed(self, now, ops):
        """喂进本轮的操作日志，now 是这次扫描的时刻，返回本批事件。"""
        final = {path: state for _, path, state in ops}
        for path, state in final.items():
            if state == self._observed.get(path):
                continue
            self._observed[path] = state
            if state == self._committed.get(path):
                self._pending.pop(path, None)
            else:
                self._pending[path] = (now, state)
        ready = [(path, state) for path, (at, state) in self._pending.items()
                 if now - at >= self.debounce]
        pairs = []
        for path, state in ready:
            del self._pending[path]
            pairs.append((path, self._committed.get(path), state))
            self._committed[path] = state
        return publish(pairs)


class OpScript:
    """在真实目录上做随机操作，把操作日志记下来。"""

    KINDS = ("create", "mkdir", "write", "append", "remove", "rename",
             "replace", "touch")

    def __init__(self, root, clock, granularity=1.0, seed=1):
        self.root = os.path.abspath(root)
        self.clock = clock
        self.granularity_ns = int(float(granularity) * 1e9)
        self.rng = random.Random(seed)
        self.files = []
        self.dirs = []
        self._seq = 0

    def _abs(self, rel):
        return os.path.join(self.root, rel) if rel else self.root

    def _name(self, parent, suffix=".txt"):
        self._seq += 1
        name = "f%03d%s" % (self._seq, suffix)
        return name if not parent else parent + "/" + name

    def _write(self, rel, data):
        with open(self._abs(rel), "wb") as handle:
            handle.write(data)

    def _pick(self):
        return self.rng.choice(self.files) if self.files else None

    def _flip(self, ops, rel):
        """把 rel 和各级祖先钉在当前时间片上，钉过的路径都记进日志。"""
        now = self.clock()
        stamp = int(now * 1e9) // self.granularity_ns * self.granularity_ns
        parts = rel.split("/")
        for index in range(len(parts), 0, -1):
            target = "/".join(parts[:index])
            try:
                os.utime(self._abs(target), ns=(stamp, stamp))
            except OSError:
                pass
            ops.append((now, target, state_of(self._abs(target))))

    def setup(self, files=12, dirs=3):
        """铺一棵初始树，每个文件落在不同的时间片上，返回全树状态。"""
        self.dirs.append("")
        for index in range(dirs):
            rel = "d%d" % index
            os.makedirs(self._abs(rel))
            self.dirs.append(rel)
        for _ in range(files):
            self.clock.advance(1.2)
            rel = self._name(self.rng.choice(self.dirs))
            self._write(rel, self.rng.randbytes(self.rng.randrange(1, 200)))
            self.files.append(rel)
            self._flip([], rel)
        return self.states()

    def step(self, n_ops=1):
        """随机做 n 个操作，返回本轮的操作日志。"""
        ops = []
        for _ in range(n_ops):
            self.clock.advance(self.rng.uniform(0.0, 0.35))
            getattr(self, "_op_" + self.rng.choice(self.KINDS))(ops)
        return ops

    def states(self):
        """整棵树当前的可观测状态，给对拍基准打底用。"""
        out = {}
        for dirpath, dirnames, filenames in os.walk(self.root):
            for name in dirnames + filenames:
                absolute = os.path.join(dirpath, name)
                rel = os.path.relpath(absolute, self.root)
                out[rel.replace(os.sep, "/")] = state_of(absolute)
        return out

    def _op_create(self, ops):
        rel = self._name(self.rng.choice(self.dirs))
        self._write(rel, self.rng.randbytes(self.rng.randrange(1, 200)))
        self.files.append(rel)
        self._flip(ops, rel)

    def _op_mkdir(self, ops):
        rel = self._name(self.rng.choice(self.dirs), ".d")
        os.makedirs(self._abs(rel))
        self.dirs.append(rel)
        self._flip(ops, rel)

    def _op_write(self, ops):
        rel = self._pick()
        if rel is not None:
            self._write(rel, self.rng.randbytes(self.rng.randrange(1, 200)))
            self._flip(ops, rel)

    def _op_append(self, ops):
        rel = self._pick()
        if rel is not None:
            with open(self._abs(rel), "ab") as handle:
                handle.write(self.rng.randbytes(1))
            self._flip(ops, rel)

    def _op_remove(self, ops):
        rel = self._pick()
        if rel is not None:
            os.remove(self._abs(rel))
            self.files.remove(rel)
            self._flip(ops, rel)

    def _op_rename(self, ops):
        rel = self._pick()
        if rel is not None:
            dest = self._name(self.rng.choice(self.dirs))
            os.rename(self._abs(rel), self._abs(dest))
            self.files.remove(rel)
            self.files.append(dest)
            self._flip(ops, rel)
            self._flip(ops, dest)

    def _op_replace(self, ops):
        rel = self._pick()
        if rel is not None:
            parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
            tmp = self._name(parent, ".tmp")
            self._write(tmp, self.rng.randbytes(self.rng.randrange(1, 200)))
            os.replace(self._abs(tmp), self._abs(rel))
            self._flip(ops, rel)

    def _op_touch(self, ops):
        rel = self._pick()
        if rel is not None:
            self._flip(ops, rel)
