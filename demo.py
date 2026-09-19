"""路由现状演示。

第一段：3 节点下固定 key 的路由表。
第二段：模拟 3 -> 4 扩容，统计有多少 key 换了归属（缓存失效的直接来源），
对比取模路由与一致性哈希路由的迁移量。
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
    print("  [取模路由]")
    print(f"    换归属的 key: {changed}/{total} ({changed * 100.0 / total:.1f}%)")
    print("    （扩缩容几乎全量迁移，命中率被打穿的根源）")

    print("  [一致性哈希，每物理节点 150 个虚拟节点]")
    hr = ConsistentHashRouter(NODES)
    for k in KEYS[:8]:
        print(f"  {k} -> {hr.route(k)}")
    hr2 = ConsistentHashRouter(NODES + [NEW_NODE])
    h_changed, h_total = migration_stats(hr, hr2)
    print(f"    换归属的 key: {h_changed}/{h_total} "
          f"({h_changed * 100.0 / h_total:.1f}%)")
    print("    （只有落到新节点环段的 key 迁移，约 1/N；老节点之间互不串扰）")
    print(f"\n  迁移量对比：取模 {changed} vs 一致性哈希 {h_changed}，"
          f"减少约 {(1 - h_changed / changed) * 100:.0f}% 的缓存失效")


if __name__ == "__main__":
    main()
