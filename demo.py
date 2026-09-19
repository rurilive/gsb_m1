"""路由现状演示。

第一段：3 节点下固定 key 的路由表。
第二段：模拟 3 -> 4 扩容，统计有多少 key 换了归属（缓存失效的直接来源）。
"""

from shard.router import ConsistentHashRouter, ModuloRouter

NODES = ["cache-1", "cache-2", "cache-3"]
NEW_NODE = "cache-4"
KEYS = [f"session:{i:04d}" for i in range(2000)]


def migration_stats(old, new):
    changed = sum(1 for k in KEYS if old.route(k) != new.route(k))
    return changed, len(KEYS)


def main():
    print("=== 路由表现状（3 节点，取模） ===")
    r = ModuloRouter(NODES)
    for k in KEYS[:8]:
        print(f"  {k} -> {r.route(k)}")

    print(f"\n=== 扩容 {len(NODES)} -> {len(NODES) + 1}（加入 {NEW_NODE}） ===")
    r2 = ModuloRouter(NODES + [NEW_NODE])
    changed, total = migration_stats(r, r2)
    print(f"  换归属的 key: {changed}/{total} ({changed * 100.0 / total:.1f}%)")
    print("  （扩缩容几乎全量迁移，命中率被打穿的根源）")

    print(f"\n=== 对比：一致性哈希扩容 {len(NODES)} -> {len(NODES) + 1} ===")
    c1 = ConsistentHashRouter(NODES)
    c2 = ConsistentHashRouter(NODES + [NEW_NODE])
    changed2, total2 = migration_stats(c1, c2)
    print(f"  换归属的 key: {changed2}/{total2} ({changed2 * 100.0 / total2:.1f}%)")
    print(f"  取模路由迁移 {changed} 个 vs 一致性哈希迁移 {changed2} 个，"
          f"迁移量降为原来的 {changed2 * 100.0 / changed:.1f}%")


if __name__ == "__main__":
    main()
