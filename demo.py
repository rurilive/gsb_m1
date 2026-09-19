"""mvstore 现状演示。

第一段：内存模式的基本读写。
第二段：落盘模式与重启恢复。
文末注释：预留的事务演示位子。
"""

import os
import tempfile

from mvstore.store import Store


def main():
    print("=== 内存模式 ===")
    kv = Store()
    kv.put("feature.flag", {"enabled": True, "rollout": 30})
    kv.put("feature.name", "mvcc")
    print(f"  get('feature.flag') -> {kv.get('feature.flag')}")
    kv.delete("feature.name")
    print(f"  get('feature.name') -> {kv.get('feature.name')}")

    print("\n=== 落盘与恢复 ===")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "store.log")
        s1 = Store(path)
        s1.put("owner", "cache-team")
        s1.put("quota", 128)
        s1.delete("quota")
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                print(f"  log: {line.strip()}")
        s2 = Store(path)
        print(f"  重启后 get('owner') -> {s2.get('owner')}")
        print(f"  重启后 get('quota') -> {s2.get('quota')}")

    # TODO(事务改造): MVCC 实现后，在这里加一段两事务冲突演示：
    # 两个事务先后 begin、读同一个 key、各自 put 后提交，
    # 先提交者生效，后提交者抛 ConflictError，直观展示冲突检测。


if __name__ == "__main__":
    main()
