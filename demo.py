"""mvstore 演示。

第一段：内存模式的基本读写。
第二段：落盘模式与重启恢复。
第三段：两事务写冲突（first-committer-wins）演示。
"""

import os
import tempfile

from mvstore import ConflictError, Store


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

    print("\n=== 事务写冲突 ===")
    mvcc = Store()
    mvcc.put("config.timeout", 30)

    tx1 = mvcc.begin()
    tx2 = mvcc.begin()
    print(f"  tx1 读快照 get -> {tx1.get('config.timeout')}")
    print(f"  tx2 读快照 get -> {tx2.get('config.timeout')}")

    tx1.put("config.timeout", 45)
    v1 = tx1.commit()
    print(f"  tx1 提交成功，全局版本推进到 {v1}")

    tx2.put("config.timeout", 60)
    try:
        tx2.commit()
    except ConflictError as exc:
        print(f"  tx2 提交被拒：ConflictError（{exc}），事务作废")
    print(f"  最终 get('config.timeout') -> {mvcc.get('config.timeout')}")


if __name__ == "__main__":
    main()
