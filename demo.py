"""buildplan 演示：解析清单 -> 分层 -> 模拟执行 -> 报告。

演示清单里把 tools 放进 fail_targets，展示 failed 到 skip 的级联。
"""

from buildplan import Executor, parse_manifest

MANIFEST = """\
# demo 项目的构建清单
base:
core: base
net: base
server: core net
tools: core
tests: server tools
docs: tests
"""


def main():
    manifest = parse_manifest(MANIFEST)
    executor = Executor(fail_targets={"tools"})
    report = executor.run(manifest)
    print(report.text)
    print("（tools 失败后，依赖它的 tests、docs 被级联跳过）")

    # TODO(plan 模式): plan 能力就位后，在这里用同一份清单输出执行计划，
    # 与上面的执行报告对照：分层与并行组一致，但不触发任何模拟动作。


if __name__ == "__main__":
    main()
