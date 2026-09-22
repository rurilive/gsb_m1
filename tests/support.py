"""测试用的共享小工具：起一个真的拿住锁的子进程。"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HOLDER = """
import sys
from xlock import FileLock

lock = FileLock(sys.argv[1], poll=0.02)
assert lock.acquire(timeout=5)
print("LOCKED", flush=True)
sys.stdin.readline()
lock.release()
"""


def child_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return env


def spawn_holder(path, children):
    """起个真子进程拿住 path，登记进 children，等它回报 LOCKED。"""
    proc = subprocess.Popen(
        [sys.executable, "-c", HOLDER, path],
        cwd=ROOT, env=child_env(), stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, universal_newlines=True)
    children.append(proc)
    assert proc.stdout.readline().strip() == "LOCKED"
    return proc


def reap(children):
    """收掉测试里起过的子进程。"""
    for proc in children:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        for stream in (proc.stdin, proc.stdout):
            if stream is not None:
                stream.close()
