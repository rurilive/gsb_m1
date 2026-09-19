"""verkit 功能演示。

第一段：典型版本号的解析结果。
第二段：把依赖候选按 semver 优先级排序（含 prerelease）。
第三段：用区间文本过滤候选并挑出 best()。
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

    print("\n=== 区间匹配（^1.2.0 || >=2.0.0） ===")
    rng = parse_range("^1.2.0 || >=2.0.0")
    for s in LOCKFILE:
        print(f"  {s:<22} match={match(s, rng)}")
    print(f"  best = {best(LOCKFILE, rng)}")

    print("\n=== prerelease 放行（^1.4.2-beta.1） ===")
    rng = parse_range("^1.4.2-beta.1")
    for s in LOCKFILE:
        if match(s, rng):
            print(f"  {s:<22} 命中")
    print(f"  best = {best(LOCKFILE, rng)}")


if __name__ == "__main__":
    main()
