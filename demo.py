"""路径匹配现状演示。

第一段：段级 glob 的行为（* 不跨段、段数对齐）。
第二段：把源码树里的一批路径按几种 pattern 逐条过一遍。
"""

from pathmatch.match import match

PATTERNS = ["*.py", "src/*.py", "src/*/*.py", "assets/*", "docs/*.md"]
TREE = [
    "main.py",
    "src/main.py",
    "src/core/engine.py",
    "src/util/log.py",
    "assets/logo.svg",
    "docs/notes.md",
    "build.log",
]


def main():
    print("=== 段级 glob：* 不跨段，段数必须对齐 ===")
    for pat in PATTERNS:
        hits = [p for p in TREE if match(pat, p)]
        print(f"  {pat:<12} 命中 {len(hits)} 条")
        for h in hits:
            print(f"      {h}")

    print("\n=== 逐条判定（pattern=src/*.py） ===")
    for p in TREE:
        print(f"  {str(match('src/*.py', p)):<5} {p}")

    # TODO(.gitignore 语义): IgnoreRules 实现后，在这里用一组
    # .gitignore 规则（含否定、目录限定、嵌套优先）重新过滤这批路径，
    # 展示每条是 ignored 还是 allowed，以及决定性的那条规则。


if __name__ == "__main__":
    main()
