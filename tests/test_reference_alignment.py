"""Watcher 与 OpReference 对拍，以及四类故障现场的回归测试。

老测试只锁旧接口，这里锁修复后的语义：
- 随机操作序列 + 随机扫描时机，事件集合与顺序逐批对齐 OpReference；
- 原子保存、连写合并、粗时间戳同长改写、目录权限瞬断四个现场；
- moved 配对、改名盖住已有路径、整目录移动、一轮内出现又消失；
- 静止的树扫描不读文件内容。
"""

import os
import random
import tempfile
import time
import unittest

from snapwatch import (CREATED, DELETED, MODIFIED, MOVED, Event, ManualClock,
                       OpReference, OpScript, PollScanner, SysFS, Watcher,
                       publish, sort_key, state_of)


def make_file(root, rel, data, clock, stamp=None):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    value = int((clock() if stamp is None else stamp) * 1e9)
    os.utime(path, ns=(value, value))
    return path


def drain(watcher, reference, clock, ops, step=2.0):
    clock.advance(step)
    got = watcher.poll()
    expected = reference.feed(clock(), ops)
    return got, expected


class CountingFS(SysFS):
    """统计 read_bytes 调用次数，用来保证静止时不读文件内容。"""

    def __init__(self):
        self.reads = 0

    def read_bytes(self, path):
        self.reads += 1
        return super().read_bytes(path)


class BlockedFS(SysFS):
    def __init__(self, name):
        self.name = name
        self.blocked = False

    def scandir(self, path):
        if self.blocked and path.endswith(os.sep + self.name):
            raise PermissionError(path)
        return super().scandir(path)


def run_random_alignment(seed, rounds=70, files=10, dirs=3):
    rng = random.Random(seed * 7919 + 13)
    with tempfile.TemporaryDirectory() as root:
        clock = ManualClock(1000.0)
        script = OpScript(root, clock, granularity=1.0, seed=seed)
        states = script.setup(files=files, dirs=dirs)
        watcher = Watcher(root, fs=SysFS(), clock=clock,
                          debounce=0.25, granularity=1.0)
        reference = OpReference(debounce=0.25)
        reference.prime(states)

        # 打底快照没读过内容，先静默收编，之后两边基准一致
        got, expected = drain(watcher, reference, clock, [])
        assert got == expected, (seed, got, expected)

        for round_index in range(rounds):
            pending_ops = []
            for _ in range(rng.randint(1, 4)):
                pending_ops.extend(script.step(1))
                # 随机扫描时机：有的操作后立刻扫，有的攒到后面一起对
                if rng.random() < 0.6:
                    got = watcher.poll()
                    expected = reference.feed(clock(), pending_ops)
                    pending_ops = []
                    assert got == expected, (
                        seed, round_index,
                        sorted(map(repr, got)), sorted(map(repr, expected)))
            got = watcher.poll()
            expected = reference.feed(clock(), pending_ops)
            assert got == expected, (
                seed, round_index,
                sorted(map(repr, got)), sorted(map(repr, expected)))
            if round_index % 7 == 6:
                # 静默一段时间，让待确认事件两边同时到期
                got, expected = drain(watcher, reference, clock, [])
                assert got == expected, (seed, got, expected)

        for _ in range(5):
            got, expected = drain(watcher, reference, clock, [])
            assert got == expected, (seed, got, expected)
        assert watcher.poll() == []


class TestReferenceAlignment(unittest.TestCase):
    def test_random_sequences_match_reference(self):
        for seed in range(1, 26):
            run_random_alignment(seed)


class TestAtomicSave(unittest.TestCase):
    def test_tmp_then_replace_is_one_modified(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "notes.txt", b"v1", clock)
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            clock.advance(1.0)
            self.assertEqual(watcher.poll(), [])
            tmp = make_file(root, "notes.txt.tmp", b"v2", clock)
            os.replace(tmp, os.path.join(root, "notes.txt"))
            clock.advance(1.0)
            self.assertEqual(watcher.poll(), [])  # 锚定本轮变化
            clock.advance(1.0)
            self.assertEqual(watcher.poll(),
                             [Event(MODIFIED, "notes.txt", False)])

    def test_tmp_visible_between_polls_still_reports_modified(self):
        # tmp 在某轮扫到过、替换在更后面发生：tmp 自身净效果是删除
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "notes.txt", b"v1", clock)
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            clock.advance(1.0)
            watcher.poll()
            make_file(root, "notes.txt.tmp", b"v2", clock)
            clock.advance(0.1)
            watcher.poll()  # tmp 被扫到，但还在静默期
            os.replace(os.path.join(root, "notes.txt.tmp"),
                       os.path.join(root, "notes.txt"))
            clock.advance(1.0)
            self.assertEqual(watcher.poll(), [])
            clock.advance(1.0)
            self.assertEqual(watcher.poll(),
                             [Event(MODIFIED, "notes.txt", False)])

    def test_tmp_published_then_replaced_reports_delete_too(self):
        # tmp 已经单独发布成 created，之后才替换：tmp 删除 + notes 修改
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "notes.txt", b"v1", clock)
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            clock.advance(1.0)
            watcher.poll()
            make_file(root, "notes.txt.tmp", b"v2", clock)
            clock.advance(1.0)
            self.assertEqual(watcher.poll(), [])
            clock.advance(1.0)
            self.assertEqual(watcher.poll(),
                             [Event(CREATED, "notes.txt.tmp", False)])
            os.replace(os.path.join(root, "notes.txt.tmp"),
                       os.path.join(root, "notes.txt"))
            clock.advance(1.0)
            self.assertEqual(watcher.poll(), [])
            clock.advance(1.0)
            self.assertEqual(watcher.poll(),
                             [Event(DELETED, "notes.txt.tmp", False),
                              Event(MODIFIED, "notes.txt", False)])


class TestCoalescing(unittest.TestCase):
    def test_repeated_writes_merge_to_one(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "n.txt", b"v1", clock)
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            clock.advance(2.0)
            watcher.poll()
            for content in (b"v2", b"v3", b"v4"):
                clock.advance(0.1)
                make_file(root, "n.txt", content, clock)
                self.assertEqual(watcher.poll(), [])
            clock.advance(1.0)
            self.assertEqual(watcher.poll(),
                             [Event(MODIFIED, "n.txt", False)])

    def test_appear_and_disappear_within_round_is_silent(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            path = make_file(root, "ghost.txt", b"x", clock)
            os.remove(path)
            clock.advance(2.0)
            self.assertEqual(watcher.poll(), [])

    def test_debounce_timer_resets_on_new_change(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "n.txt", b"v1", clock)
            watcher = Watcher(root, fs=SysFS(), clock=clock,
                              debounce=0.5)
            clock.advance(2.0)
            watcher.poll()
            make_file(root, "n.txt", b"v2", clock)
            clock.advance(0.3)
            self.assertEqual(watcher.poll(), [])
            clock.advance(0.3)
            make_file(root, "n.txt", b"v3", clock)
            self.assertEqual(watcher.poll(), [])
            clock.advance(0.4)
            self.assertEqual(watcher.poll(), [])
            clock.advance(0.2)
            self.assertEqual(watcher.poll(),
                             [Event(MODIFIED, "n.txt", False)])


class TestCoarseTimestamps(unittest.TestCase):
    def test_same_second_same_size_double_write_not_missed(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "build.log", b"aaaaaaaa", clock)
            fs = CountingFS()
            watcher = Watcher(root, fs=fs, clock=clock, granularity=1.0)
            clock.advance(2.0)
            watcher.poll()
            for content in (b"bbbbbbbb", b"cccccccc"):
                clock.advance(0.2)
                make_file(root, "build.log", content, clock, stamp=500.0)
            clock.advance(0.2)
            self.assertEqual(watcher.poll(), [])
            clock.advance(1.0)
            self.assertEqual(watcher.poll(),
                             [Event(MODIFIED, "build.log", False)])


class TestBlockedDirectory(unittest.TestCase):
    def _build(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = tmp.name
        clock = ManualClock(500.0)
        for name in ("f1.txt", "f2.txt", "f3.txt"):
            make_file(root, "d0/" + name, b"x", clock)
        fs = BlockedFS("d0")
        watcher = Watcher(root, fs=fs, clock=clock)
        clock.advance(2.0)
        watcher.poll()
        return root, fs, clock, watcher

    def test_chmod_does_not_report_subtree_deleted(self):
        _, fs, clock, watcher = self._build()
        fs.blocked = True
        clock.advance(2.0)
        self.assertEqual(watcher.poll(), [])
        clock.advance(2.0)
        self.assertEqual(watcher.poll(), [])

    def test_recovery_reports_real_change(self):
        root, fs, clock, watcher = self._build()
        fs.blocked = True
        clock.advance(2.0)
        watcher.poll()
        fs.blocked = False
        make_file(root, "d0/f4.txt", b"y", clock)
        clock.advance(2.0)
        self.assertEqual(watcher.poll(), [])
        clock.advance(2.0)
        self.assertEqual(watcher.poll(),
                         [Event(MODIFIED, "d0", True),
                          Event(CREATED, "d0/f4.txt", False)])


class TestMovedSemantics(unittest.TestCase):
    def test_rename_over_existing_path_is_delete_plus_modified(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "a.txt", b"aaaa", clock)
            make_file(root, "b.txt", b"bbbb", clock)
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            clock.advance(2.0)
            watcher.poll()
            os.rename(os.path.join(root, "a.txt"),
                      os.path.join(root, "b.txt"))
            clock.advance(2.0)
            self.assertEqual(watcher.poll(), [])
            clock.advance(2.0)
            self.assertEqual(watcher.poll(),
                             [Event(DELETED, "a.txt", False),
                              Event(MODIFIED, "b.txt", False)])

    def test_directory_move_pairs_every_entry(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "d/f1.txt", b"1", clock)
            make_file(root, "d/f2.txt", b"22", clock)
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            clock.advance(2.0)
            watcher.poll()
            os.rename(os.path.join(root, "d"), os.path.join(root, "e"))
            clock.advance(2.0)
            self.assertEqual(watcher.poll(), [])
            clock.advance(2.0)
            events = watcher.poll()
            expected = [
                Event(MOVED, "d", True, "e"),
                Event(MOVED, "d/f1.txt", False, "e/f1.txt"),
                Event(MOVED, "d/f2.txt", False, "e/f2.txt"),
            ]
            self.assertEqual(events, expected)


class TestBatchOrder(unittest.TestCase):
    def test_order_matches_sort_key_against_publish(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(500.0)
            make_file(root, "d/sub/f.txt", b"old", clock)
            make_file(root, "m.txt", b"m", clock)
            make_file(root, "s.txt", b"s", clock)
            watcher = Watcher(root, fs=SysFS(), clock=clock)
            clock.advance(2.0)
            watcher.poll()

            def states():
                out = {}
                for dirpath, dirnames, filenames in os.walk(root):
                    for name in dirnames + filenames:
                        absolute = os.path.join(dirpath, name)
                        rel = os.path.relpath(
                            absolute, root).replace(os.sep, "/")
                        out[rel] = state_of(absolute)
                return out

            before = states()
            os.remove(os.path.join(root, "d/sub/f.txt"))
            make_file(root, "m.txt", b"MMMMMM", clock)
            os.rename(os.path.join(root, "s.txt"),
                      os.path.join(root, "t.txt"))
            make_file(root, "d/sub/new.txt", b"n", clock)
            after = states()

            pairs = []
            for path in set(before) | set(after):
                if before.get(path) != after.get(path):
                    pairs.append((path, before.get(path), after.get(path)))
            expected = publish(pairs)

            clock.advance(2.0)
            self.assertEqual(watcher.poll(), [])
            clock.advance(2.0)
            self.assertEqual(watcher.poll(), expected)
            self.assertEqual(expected, sorted(expected, key=sort_key))


class TestQuietTreePerformance(unittest.TestCase):
    def _populate(self, root, count, clock):
        for index in range(count):
            sub = "d%02d" % (index % 50)
            make_file(root, "%s/f%05d.txt" % (sub, index),
                      b"x" * (index % 64), clock, stamp=900.0)

    def test_scanner_never_reads_file_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(1000.0)
            self._populate(root, 500, clock)
            fs = CountingFS()
            snapshot = PollScanner(fs, root).scan()
            self.assertGreater(len(snapshot), 500)
            self.assertEqual(fs.reads, 0)

    def test_quiet_watcher_poll_reads_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(1000.0)
            self._populate(root, 3000, clock)
            fs = CountingFS()
            watcher = Watcher(root, fs=fs, clock=clock, granularity=1.0)
            self.assertEqual(fs.reads, 0)
            start = time.time()
            clock.advance(2.0)
            self.assertEqual(watcher.poll(), [])
            clock.advance(2.0)
            self.assertEqual(watcher.poll(), [])
            self.assertLess(time.time() - start, 3.0)
            self.assertEqual(fs.reads, 0)

    def test_changed_file_read_only_once_until_settled(self):
        with tempfile.TemporaryDirectory() as root:
            clock = ManualClock(1000.0)
            self._populate(root, 200, clock)
            fs = CountingFS()
            watcher = Watcher(root, fs=fs, clock=clock, granularity=1.0)
            make_file(root, "hot.txt", b"v1", clock, stamp=999.5)
            clock.advance(0.2)
            watcher.poll()  # 新文件，读一次内容
            reads_after_create = fs.reads
            make_file(root, "hot.txt", b"v2", clock, stamp=999.5)
            clock.advance(0.2)
            watcher.poll()  # 同时间片同长改写，再读一次才能发现
            self.assertEqual(fs.reads, reads_after_create + 1)
            # 首次出现的 mtime 永远不能缓存（防止同时间片连写被挡），
            # 再写一笔拿到新 mtime、熬过时间片后才进入缓存
            make_file(root, "hot.txt", b"v3", clock, stamp=1004.0)
            clock.advance(2.0)
            watcher.poll()
            clock.advance(2.0)
            watcher.poll()
            reads_when_settled = fs.reads
            clock.advance(2.0)
            watcher.poll()
            self.assertEqual(fs.reads, reads_when_settled)



class TestInaccessibleRoot(unittest.TestCase):
    def test_root_scandir_failure_keeps_whole_tree(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = tmp.name
        clock = ManualClock(500.0)
        make_file(root, "a.txt", b"a", clock)
        make_file(root, "d/b.txt", b"b", clock)

        class RootBlocked(SysFS):
            def __init__(self):
                self.blocked = False

            def scandir(self, path):
                if self.blocked and os.path.abspath(path) == os.path.abspath(
                        root):
                    raise PermissionError(path)
                return super().scandir(path)

        fs = RootBlocked()
        watcher = Watcher(root, fs=fs, clock=clock)
        clock.advance(2.0)
        watcher.poll()
        fs.blocked = True
        clock.advance(2.0)
        self.assertEqual(watcher.poll(), [])
        self.assertEqual(
            sorted(watcher.snapshot().entries), ["a.txt", "d", "d/b.txt"])
        fs.blocked = False
        clock.advance(2.0)
        self.assertEqual(watcher.poll(), [])


if __name__ == "__main__":
    unittest.main()
