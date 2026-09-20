"""IdempotentSubmitter 行为测试。

覆盖：同键复用、重启重放（新实例指向同一目录）、
并发同键单执行（线程 + Event 定节奏）、过期重跑（拨快时钟）。
"""

import json
import os
import threading
import unittest

from idemkit import Dispatcher
from idemkit.idempotent import IdempotentSubmitter


class FakeClock:
    """可注入时钟：单调时间，测试里手动拨快。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class IdemTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = self._tmpdir()
        self.clock = FakeClock()
        self.dispatcher = Dispatcher()
        self.calls = []

        def counting(payload):
            self.calls.append(payload)
            return {"echo": payload, "seq": len(self.calls)}

        self.dispatcher.register("counting", counting)

    def _tmpdir(self):
        import tempfile

        return tempfile.mkdtemp(prefix="idemkit-")

    def submitter(self, ttl=3600):
        return IdempotentSubmitter(
            self.dispatcher, self.tmpdir, ttl, clock=self.clock
        )


class TestSameKeyReuse(IdemTestBase):
    def test_same_key_returns_first_result(self):
        s = self.submitter()
        first = s.submit("key-1", "counting", {"n": 1})
        second = s.submit("key-1", "counting", {"n": 2})
        third = s.submit("key-1", "counting", {"n": 3})

        self.assertEqual(first, {"echo": {"n": 1}, "seq": 1})
        # 后续提交拿到的都是首跑结果（含首跑 payload）
        self.assertEqual(second, first)
        self.assertEqual(third, first)
        self.assertEqual(self.calls, [{"n": 1}])

    def test_different_keys_run_separately(self):
        s = self.submitter()
        r1 = s.submit("key-a", "counting", {"n": 1})
        r2 = s.submit("key-b", "counting", {"n": 2})
        self.assertEqual(r1, {"echo": {"n": 1}, "seq": 1})
        self.assertEqual(r2, {"echo": {"n": 2}, "seq": 2})
        self.assertEqual(len(self.calls), 2)

    def test_record_file_shape(self):
        s = self.submitter(ttl=60)
        s.submit("key-1", "counting", {"n": 1})
        files = [n for n in os.listdir(self.tmpdir) if n.endswith(".json")]
        self.assertEqual(len(files), 1)
        with open(os.path.join(self.tmpdir, files[0]), encoding="utf-8") as f:
            record = json.load(f)
        self.assertEqual(
            set(record), {"idem_key", "result", "expires_at"}
        )
        self.assertEqual(record["idem_key"], "key-1")
        self.assertEqual(record["result"], {"echo": {"n": 1}, "seq": 1})
        self.assertEqual(record["expires_at"], 1060.0)


class TestRestartReplay(IdemTestBase):
    def test_new_instance_same_dir_replays(self):
        s1 = self.submitter()
        first = s1.submit("key-1", "counting", {"n": 1})

        # 模拟进程重启：新 submitter、新 dispatcher，指向同一目录
        new_dispatcher = Dispatcher()
        new_calls = []
        new_dispatcher.register(
            "counting", lambda p: new_calls.append(p) or {"fresh": True}
        )
        s2 = IdempotentSubmitter(
            new_dispatcher, self.tmpdir, 3600, clock=self.clock
        )
        replayed = s2.submit("key-1", "counting", {"n": 9})

        self.assertEqual(replayed, first)
        self.assertEqual(new_calls, [])


class TestConcurrentSameKey(IdemTestBase):
    def test_concurrent_same_key_runs_handler_once(self):
        entered = threading.Event()
        release = threading.Event()

        def gated(payload):
            # 通知主线程 handler 已进入，再等放行，制造同键并发窗口
            entered.set()
            release.wait(5)
            self.calls.append(payload)
            return {"echo": payload, "seq": len(self.calls)}

        self.dispatcher.register("gated", gated)
        s = self.submitter()
        results = []

        def worker(payload):
            results.append(s.submit("hot-key", "gated", payload))

        t1 = threading.Thread(target=worker, args=({"n": 1},))
        t2 = threading.Thread(target=worker, args=({"n": 2},))
        t3 = threading.Thread(target=worker, args=({"n": 3},))
        t1.start()
        self.assertTrue(entered.wait(5), "handler 未在预期时间内进入")
        # 首跑已在 handler 里卡住，此时启动同键并发提交
        t2.start()
        t3.start()
        release.set()
        t1.join(5)
        t2.join(5)
        t3.join(5)

        self.assertEqual(self.calls, [{"n": 1}])
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(results[0], {"echo": {"n": 1}, "seq": 1})


class TestExpiry(IdemTestBase):
    def test_expired_key_reruns_and_lazy_cleans(self):
        s = self.submitter(ttl=60)
        first = s.submit("key-1", "counting", {"n": 1})

        self.clock.advance(30)
        self.assertEqual(
            s.submit("key-1", "counting", {"n": 2}), first
        )
        self.assertEqual(len(self.calls), 1)

        # 过期后同键重跑，拿到新结果
        self.clock.advance(31)
        second = s.submit("key-1", "counting", {"n": 2})
        self.assertEqual(second, {"echo": {"n": 2}, "seq": 2})
        self.assertEqual(self.calls, [{"n": 1}, {"n": 2}])

    def test_lazy_purge_removes_other_expired_files(self):
        s = self.submitter(ttl=60)
        s.submit("old-key", "counting", {"n": 1})
        s.submit("new-key", "counting", {"n": 2})
        self.assertEqual(
            len([n for n in os.listdir(self.tmpdir) if n.endswith(".json")]),
            2,
        )

        self.clock.advance(61)
        # 一个全新键的读写顺手把两个过期文件都清掉
        s.submit("fresh-key", "counting", {"n": 3})
        remaining = [
            n for n in os.listdir(self.tmpdir) if n.endswith(".json")
        ]
        self.assertEqual(len(remaining), 1)
        with open(
            os.path.join(self.tmpdir, remaining[0]), encoding="utf-8"
        ) as f:
            record = json.load(f)
        self.assertEqual(record["idem_key"], "fresh-key")


if __name__ == "__main__":
    unittest.main()
