"""snapwatch 现状演示：四类现场各跑一遍，看现在报出来的事件。
时间戳都用假时钟钉死，好复现，不靠真机的时钟精度。
"""

import os
import tempfile

from snapwatch import ManualClock, SysFS, Watcher


def make_file(root, rel, data, clock, stamp=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    value = int((clock() if stamp is None else stamp) * 1e9)
    os.utime(path, ns=(value, value))
    return path


def poll_rounds(watcher, clock, rounds=3, step=1.0):
    events = []
    for _ in range(rounds):
        clock.advance(step)
        events.extend(watcher.poll())
    return events


def show(title, events):
    body = "".join("    %r\n" % event for event in events)
    print("  %s：报出 %d 条\n%s" % (title, len(events), body), end="")


def scene_atomic_save():
    print("=== 1. 编辑器原子保存：先写 notes.txt.tmp 再改名盖上去 ===")
    with tempfile.TemporaryDirectory() as root:
        clock = ManualClock(500.0)
        make_file(root, "notes.txt", b"v1", clock)
        watcher = Watcher(root, fs=SysFS(), clock=clock)
        poll_rounds(watcher, clock)
        tmp = make_file(root, "notes.txt.tmp", b"v2", clock)
        os.replace(tmp, os.path.join(root, "notes.txt"))
        show("保存之后", poll_rounds(watcher, clock))


def scene_save_storm():
    print("=== 2. 一次保存里连写三笔，中间各有一次扫描 ===")
    with tempfile.TemporaryDirectory() as root:
        clock = ManualClock(500.0)
        make_file(root, "notes.txt", b"v1", clock)
        watcher = Watcher(root, fs=SysFS(), clock=clock)
        poll_rounds(watcher, clock)
        events = []
        for content in (b"v2", b"v3", b"v4"):
            clock.advance(1.2)
            make_file(root, "notes.txt", content, clock)
            events.extend(watcher.poll())
        events.extend(poll_rounds(watcher, clock))
        show("三笔写完", events)


def scene_coarse_timestamps():
    print("=== 3. 秒级时间戳的盘：同一秒里连改两笔，长度一样 ===")
    with tempfile.TemporaryDirectory() as root:
        clock = ManualClock(500.0)
        make_file(root, "build.log", b"aaaaaaaa", clock)
        watcher = Watcher(root, fs=SysFS(), clock=clock)
        poll_rounds(watcher, clock, rounds=2, step=0.2)
        for content in (b"bbbbbbbb", b"cccccccc"):
            clock.advance(0.2)
            make_file(root, "build.log", content, clock, stamp=500.0)
        show("第二次改写", poll_rounds(watcher, clock, step=0.2))


class BlockedFS(SysFS):
    """模拟被监听目录被 chmod 掉：scandir 直接抛权限错误。"""

    def __init__(self, name):
        self.name = name
        self.blocked = False

    def scandir(self, path):
        if self.blocked and path.endswith(os.sep + self.name):
            raise PermissionError(path)
        return super().scandir(path)


def scene_blocked_directory():
    print("=== 4. d0 被 chmod 掉，里面的文件没动过 ===")
    with tempfile.TemporaryDirectory() as root:
        clock = ManualClock(500.0)
        for name in ("f1.txt", "f2.txt", "f3.txt"):
            make_file(root, "d0/" + name, b"x", clock)
        filesystem = BlockedFS("d0")
        watcher = Watcher(root, fs=filesystem, clock=clock)
        poll_rounds(watcher, clock)
        filesystem.blocked = True
        show("chmod 之后", poll_rounds(watcher, clock))


def main():
    for scene in (scene_atomic_save, scene_save_storm, scene_coarse_timestamps,
                  scene_blocked_directory):
        scene()
        print()


if __name__ == "__main__":
    main()
