"""orchestra 现状演示。

第一段：用 Runner 串一条直线流程，看顺序执行与 context 合并。
第二段：预留的分支、并行、补偿与状态机演示位子（见文末注释）。
"""

from orchestra import Runner


def main():
    print("=== 顺序执行（现有能力） ===")
    r = Runner()
    r.add_step("fetch", lambda ctx: {"raw": "42"})
    r.add_step("parse", lambda ctx: {"value": int(ctx["raw"])})
    r.add_step("double", lambda ctx: {"value": ctx["value"] * 2})
    ctx = r.execute()
    print("  执行顺序:", r.executed)
    print("  产出上下文:", ctx)

    r2 = Runner()
    r2.add_step("fetch", lambda ctx: {"raw": "7"})
    r2.add_step(
        "parse",
        lambda ctx: (_ for _ in ()).throw(ValueError("坏数据")),
    )
    r2.add_step("double", lambda ctx: {"value": ctx["value"] * 2})
    try:
        r2.execute()
    except ValueError as exc:
        print("  步骤失败即停，已执行:", r2.executed, "原因:", exc)

    # TODO(编排器改造): 分支、并行汇聚、补偿事务、状态机与检查点重试补齐后，
    # 在这里加一段含分支与补偿的流程演示：
    # 建一台 Orchestrator，登记若干步骤并给其中一步挂条件分支，让 predicate
    # 按 context 选下游；给参与事务的步骤声明补偿动作，故意让分支后的某一步
    # 失败，观察已完成步骤被逆序补偿、状态回落为 compensated；
    # 再演示一次从检查点重试，已成功的步骤不重跑。

    # TODO(并行与超时): 并行汇聚与超时补齐后，在这里加一段演示：
    # 让一个步骤同时挂多个下游，用线程池并发跑完再汇聚；
    # 给一个慢步骤配小超时，注入假时钟推进，观察超时按失败处理并触发补偿。

    # TODO(环路与无起点): 图校验补齐后，在这里加一段演示：
    # 构造一个环，捕获 CycleError 打印它的 nodes 属性；
    # 构造一张没有起点的流程，观察定义期 fail fast。


if __name__ == "__main__":
    main()