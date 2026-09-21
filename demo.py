"""verkit 现状演示。

第一段：典型版本号的解析结果。
第二段：把依赖候选按 semver 优先级排序（含 prerelease）。
"""

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

    # TODO(区间支持): 实现区间匹配后，在这里用同一批候选版本演示
    # 按区间文本过滤和 best() 挑选，直观展示哪些版本落在 ^1.2.0 || >=2.0.0 里。


if __name__ == "__main__":
    main()
