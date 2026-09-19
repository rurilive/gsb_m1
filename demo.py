"""跳表基本用法演示（检索侧联调用的那套）。"""

from skiplist.skiplist import SkipList

sl = SkipList()

print("=== 写入与全量扫描 ===")
items = [(88, "alice"), (72, "bob"), (95, "carol"), (60, "dave"), (81, "erin")]
for score, name in items:
    sl.insert(score, name)

for key, name in sl.range_scan():
    print("  %d  %s" % (key, name))

print("\n=== 区间扫描 [75, 90] ===")
print(sl.range_scan(75, 90))

print("\n=== 点查 ===")
for target in (81, 70):
    print("  find(%d) -> %r" % (target, sl.find(target)))

print("\nsize:", len(sl))
