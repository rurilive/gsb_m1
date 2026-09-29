"""hashring 现状演示。

第一段：朴素取模分片下加节点与 lookup 的确定性，以及加节点后 key 归属的
大面积变化。
第二段：预留的哈希环、虚拟节点、权重与最小重映射演示位子（见文末注释）。
"""

from hashring.modulo import ModuloSharding

KEYS = [f"user-{i}" for i in range(1000)]


def main():
    print("=== 取模分片（现有能力） ===")
    shard = ModuloSharding(["node-a", "node-b", "node-c"])
    before = [shard.lookup(k) for k in KEYS]
    counts = {}
    for owner in before:
        counts[owner] = counts.get(owner, 0) + 1
    for node in sorted(counts):
        print(f"  {node}: {counts[node]} keys")

    shard.add_node("node-d")
    after = [shard.lookup(k) for k in KEYS]
    moved = sum(1 for a, b in zip(before, after) if a != b)
    print(f"  加 node-d 后改归属的 key: {moved} / {len(KEYS)}")

    print("  空分片 lookup ->", ModuloSharding().lookup("any"))

    # TODO(哈希环与最小重映射): 哈希环实现之后，在这里加一段演示：同一批 key
    # 在带虚拟节点的环上的归属，以及加入一个新节点后只有落在被影响区间的 key
    # 改归属、其余 key 一个不动，打印改归属的 key 数占总数的比例。


if __name__ == "__main__":
    main()
