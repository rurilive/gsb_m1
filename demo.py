"""verkit 现状演示。

第一段：典型版本号的解析结果。
第二段：把依赖候选按 semver 优先级排序（含 prerelease）。
第三段：按版本区间过滤候选，并用 best() 取满足区间的最高版本。
"""

from verkit.range import best, match, parse_range
from verkit.version import compare, parse_version

LOCKFILE = [
    "1.4.2",
    "1.4.2-beta.3",
    "1.10.0",
    "1.9.9",
    "2.0.0-rc.1",
    "2.0.0-rc.1+build.7",
    "0.9.5",
]


def main():
    print("=== 解析示例 ===")
    for s in ("1.2.3", "1.0.0-rc.1+build.5"):
        v = parse_version(s)
        print(f"  {s:<20} major={v.major} minor={v.minor} patch={v.patch} "
              f"prerelease={v.prerelease or '-'} build={v.build or '-'}")

    print("\n=== 候选版本按优先级排序 ===")
    for v in sorted(parse_version(s) for s in LOCKFILE):
        print(f"  {str(v):<20}")

    print("\n=== 两两比较（compare 返回 -1/0/1） ===")
    for a, b in [
        ("1.9.9", "1.10.0"),
        ("2.0.0-rc.1", "2.0.0-rc.1+build.7"),
        ("1.0.0", "1.0.0-alpha"),
    ]:
        print(f"  compare({a}, {b}) = {compare(a, b)}")

    print("\n=== 区间过滤（^1.2.0 || >=2.0.0） ===")
    constraint = "^1.2.0 || >=2.0.0"
    for v in sorted(parse_version(s) for s in LOCKFILE):
        mark = "命中" if match(v, constraint) else "    "
        print(f"  {mark} {str(v):<20}")
    print(f"  best() = {best(LOCKFILE, constraint)}")

    print("\n=== prerelease 放行对比 ===")
    # 默认区间不匹配 prerelease；分支里显式写出同一 x.y.z 的
    # prerelease 比较子（>=2.0.0-rc.1）后，rc 候选才会被放行。
    gate_ranges = [
        "^1.2.0 || >=2.0.0",
        "^1.2.0 || >=2.0.0-rc.1",
    ]
    for text in gate_ranges:
        parsed = parse_range(text)
        hits = [s for s in LOCKFILE if match(s, parsed)]
        print(f"  {text:<26} -> 命中: {', '.join(hits) if hits else '(无)'}")
        print(f"  {'':<26}    best: {best(LOCKFILE, parsed)}")

    print("\n=== 0.x caret 特例 ===")
    for text in ("^0.9.0", "^0.0.0"):
        print(f"  best(LOCKFILE, {text}) = {best(LOCKFILE, text)}")


if __name__ == "__main__":
    main()
