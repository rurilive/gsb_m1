"""intervaltree 基本用法演示（资源占用窗口巡检）。"""

from intervaltree import IntervalTree

tree = IntervalTree()
for lo, hi in [(10, 20), (2, 5), (40, 50), (25, 30)]:
    tree.insert(lo, hi)

print("size:", len(tree))
print("query_range(0, 100):", tree.query_range(0, 100))
print("query_range(22, 26):", tree.query_range(22, 26))
print("point_query(27):", tree.point_query(27))
print("point_query(6):", tree.point_query(6))

tree.remove(2, 5)
tree.remove(25, 30)
print("after remove:", len(tree), tree.query_range(0, 100))

try:
    tree.insert(15, 18)
except Exception as e:  # noqa: BLE001
    print("insert overlap ->", type(e).__name__)
