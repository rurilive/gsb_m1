"""演示：对一份小清单跑依赖解析，观察输出顺序与版本选择。"""
from depsolve import ResolveError, resolve

MANIFEST = {
    "unicode":    {"versions": ["1.0.0"]},
    "fmt":        {"versions": ["1.1.0", "1.2.0"], "depends": ["unicode>=0.9"]},
    "json":       {"versions": ["1.1.0", "2.0.1", "2.1.0"], "depends": ["unicode>=0.5"]},
    "cli":        {"versions": ["1.0.0"], "depends": ["fmt>=1.0", "json>=2.0"]},
    "gateway":    {"versions": ["1.0.0"], "depends": ["json>=2.0", "oldcache"]},
    "oldcache":   {"versions": ["0.9.0"], "depends": ["json<2.0"]},
    "report":     {"versions": ["2.0.0"], "depends": ["cli>=1.0", "fmt>=1.1"]},
    "archive":    {"versions": ["1.0.0"], "depends": ["json>=2.0"],
                   "optional_depends": ["archive-sse"]},
    "archive-sse": {"versions": ["0.2.0"], "depends": ["archive>=1.0"]},
}


def main():
    cases = [
        ("单个入口", ["cli"]),
        ("报告链路", ["report"]),
        ("网关链路", ["gateway"]),
        ("双入口", ["report", "gateway"]),
        ("可选组清单", ["archive"]),
    ]
    for label, requests in cases:
        try:
            order = resolve(MANIFEST, requests)
            print(f"[{label}] " + " -> ".join(order))
        except ResolveError as exc:
            print(f"[{label}] 解析失败: {exc}")
    print("演示结束")


if __name__ == "__main__":
    main()
