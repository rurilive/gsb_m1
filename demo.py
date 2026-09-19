"""路由现状演示。

第一段：3 节点下固定 key 的路由表。
第二段：模拟 3 -> 4 扩容，统计有多少 key 换了归属（缓存失效的直接来源）。
"""

from shard.router import ModuloRouter

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

    # TODO(扩容改造): 一致性哈希实现后，在这里用同一批 key 对比两种路由的迁移量，
    # 直观展示新路由只迁移必要的一小部分。


if __name__ == "__main__":
    main()
