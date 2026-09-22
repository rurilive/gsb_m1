"""xlock 现状演示：把生产上踩过的几段场景跑一遍。

每段都用小超时收尾，不会把演示挂住；带“期望”的那行是修好之后该有的
样子，跑在现在的代码上多半对不上。
"""

import os
import subprocess
import sys
import tempfile
import time

from xlock import FileLock

ROOT = os.path.dirname(os.path.abspath(__file__))

COMMON = """
import sys
import time
from xlock import FileLock, LockTimeout, ResourceGuard

def put(path, text):
    with open(path, "a") as fh:
        fh.write(text + "\\n")
"""

WORKER = COMMON + """
tag, lock_dir, out_path = sys.argv[1:4]
guard = ResourceGuard(lock_dir)
try:
    with guard.hold("journal", timeout=3):
        put(out_path, "%s 拿到锁" % tag)
        time.sleep(0.3)
        put(out_path, "%s 放开锁" % tag)
except LockTimeout:
    put(out_path, "%s 等锁超时" % tag)
"""

CRASHER = COMMON + """
import os
import signal

lock = FileLock(sys.argv[1], poll=0.02)
assert lock.acquire(timeout=5)
print("LOCKED", flush=True)
os.kill(os.getpid(), signal.SIGKILL)
"""

TAKER = COMMON + """
lock = FileLock(sys.argv[1], poll=0.02, steal_after=0)
print("接管成功" if lock.acquire(timeout=1) else "没拿到", flush=True)
time.sleep(0.3)
"""


def run(source, *args):
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen([sys.executable, "-c", source] + list(args),
                            cwd=ROOT, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, universal_newlines=True)


def crashed_worker(tmp):
    """起个 worker 拿上锁再被强杀，返回它留下的锁文件路径。"""
    path = os.path.join(tmp, "index.lock")
    proc = run(CRASHER, path)
    proc.stdout.readline()
    proc.wait(timeout=5)
    proc.stdin.close()
    proc.stdout.close()
    return path


def scenario_workers():
    print("=== 场景一：两个 worker 抢同一个资源 ===")
    with tempfile.TemporaryDirectory(prefix="xlock-demo-") as tmp:
        out = os.path.join(tmp, "journal.txt")
        workers = [run(WORKER, tag, os.path.join(tmp, "locks"), out)
                   for tag in ("w1", "w2")]
        for proc in workers:
            proc.wait(timeout=15)
        with open(out) as fh:
            print(fh.read().rstrip())
    print("  期望：两个 worker 一前一后进出，不重叠")


def scenario_crash_leftover():
    print("=== 场景二：worker 被强杀，锁文件留在了盘上 ===")
    with tempfile.TemporaryDirectory(prefix="xlock-demo-") as tmp:
        path = crashed_worker(tmp)
        print("  worker 被 SIGKILL，锁文件还在:", os.path.exists(path))
        lock = FileLock(path, poll=0.02)
        started = time.monotonic()
        got = lock.acquire(timeout=1.0)
        print("  下一个任务 acquire -> %s，耗时 %.2fs"
              % (got, time.monotonic() - started))
        print("  期望：True，把没人管的残留锁接过来")
        if got:
            lock.release()
        else:
            os.unlink(path)
            print("  现状：只能人工把锁文件删掉才能继续")


def scenario_racing_takeover():
    print("=== 场景三：刚补位的两个任务同时接管残留锁 ===")
    with tempfile.TemporaryDirectory(prefix="xlock-demo-") as tmp:
        path = crashed_worker(tmp)
        takers = [run(TAKER, path) for _ in range(2)]
        results = [proc.stdout.readline().strip() for proc in takers]
        for proc in takers:
            proc.wait(timeout=5)
        print("  两个任务各自报告:", results)
        print("  期望：只有一个接管成功，另一个让开")


def main():
    scenario_workers()
    print()
    scenario_crash_leftover()
    print()
    scenario_racing_takeover()


if __name__ == "__main__":
    main()
