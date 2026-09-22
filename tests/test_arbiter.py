"""集中式仲裁参考实现的行为基线。"""

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import support  # noqa: E402

from xlock.arbiter import ArbiterClient, CentralArbiter  # noqa: E402

CLIENT = """
import sys
import time
from xlock.arbiter import ArbiterClient

client = ArbiterClient(sys.argv[1], timeout=5)
assert client.acquire(5)
print("MINE", flush=True)
time.sleep(30)
client.release()
"""



class ArbiterTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="xlock-arb-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.sock = os.path.join(self.dir, "arb.sock")
        self.arb = CentralArbiter(self.sock).start()
        self.addCleanup(self.arb.stop)
        self.clients = []
        self.children = []
        self.addCleanup(self._reap)

    def client(self, timeout=None):
        client = ArbiterClient(self.sock, timeout=timeout)
        self.clients.append(client)
        return client

    def _reap(self):
        for client in self.clients:
            client.close()
        support.reap(self.children)

    def test_one_holder_at_a_time(self):
        first = self.client()
        second = self.client()
        self.assertFalse(second.is_held())
        self.assertTrue(first.acquire(timeout=1))
        started = time.monotonic()
        self.assertFalse(second.acquire(timeout=0.3))
        self.assertGreaterEqual(time.monotonic() - started, 0.25)
        self.assertTrue(second.is_held())
        first.release()
        self.assertFalse(second.is_held())
        self.assertTrue(second.acquire(timeout=1))
        second.release()

    def test_waiter_gets_lock_after_release(self):
        first = self.client()
        second = self.client()
        self.assertTrue(first.acquire(timeout=1))
        got = []
        thread = threading.Thread(target=lambda: got.append(second.acquire(5)))
        thread.start()
        time.sleep(0.2)
        first.release()
        thread.join(6)
        self.assertEqual(got, [True])
        second.release()

    def test_killed_client_releases(self):
        proc = subprocess.Popen(
            [sys.executable, "-c", CLIENT, self.sock],
            cwd=support.ROOT, env=support.child_env(), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, universal_newlines=True)
        self.children.append(proc)
        self.assertEqual(proc.stdout.readline().strip(), "MINE")
        proc.kill()
        proc.wait(timeout=5)
        client = self.client()
        self.assertTrue(client.acquire(timeout=3))
        client.release()

