"""测试公用：看目录树、读文件，顺手把仓库根挂上 sys.path。"""

import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def tree(root):
    """目录树快照：相对路径 -> "dir" / "file:摘要" / "link:目标"。"""
    seen = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if os.path.islink(path):
                seen[rel] = "link:" + os.readlink(path)
            elif os.path.isdir(path):
                seen[rel] = "dir"
            else:
                with open(path, "rb") as handle:
                    digest = hashlib.sha256(handle.read()).hexdigest()
                seen[rel] = "file:" + digest[:12]
    return seen


def read(root, rel):
    with open(os.path.join(root, rel), "rb") as handle:
        return handle.read()


def write(root, rel, data):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
    return path
