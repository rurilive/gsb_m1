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

    # plan 对照：同一份清单、同一个 executor，只出计划不执行。
    # 分层与并行组和上面的报告一致，但全部目标是 plan 态，
    # 不读 fail_targets，没有失败注入与级联跳过，也没有耗时。
    plan = executor.plan(manifest)
    print(plan.text)
    print("（plan 只分层不执行：无失败注入、无耗时，分层与上面报告一致）")


if __name__ == "__main__":
    main()
