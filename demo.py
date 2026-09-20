"""巡检工具包现状演示。

第一段：跑一遍 扫描 -> 核查 -> 处置 流水线。
第二段注释：结构化日志层实现后的演示位子。
"""

from loglite.checker import check
from loglite.manifest import dump, parse
from loglite.planner import plan, summary
from loglite.scanner import scan

MANIFEST = """\
# name size mtime
site.conf      2048      1758000000
notes.txt      512       1758000100
cache.tmp      65536     1758000200
site.conf      2048      1758000300
huge.blob      9437184   1758000400
editor.swp     4096      1758000500
"""


def main():
    entries = parse(MANIFEST)
    print(f"=== 巡检流水线（{len(entries)} 个条目） ===\n")

    flagged = scan(entries)
    print()
    problems = check(entries)
    print()
    actions = plan(problems)

    print("\n=== 结果 ===")
    print(f"  可疑条目: {flagged}")
    print(f"  问题清单: {problems}")
    print(f"  处置动作: {actions}")
    print(f"  动作汇总: {summary(actions)}")
    kept = [e for e in entries if e[0] not in flagged]
    print(f"\n清理后的清单预览:\n{dump(kept)}", end="")

    # TODO(结构化日志): 日志层实现后，在这里补第二段演示：
    # 三个模块的输出接到日志层后与旧 print 完全一致，
    # 再演示级别过滤、上下文字段和文件轮转。


if __name__ == "__main__":
    main()
