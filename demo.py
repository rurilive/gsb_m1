"""sagakit 现状演示。

第一段：跑一个顺序步骤序列，观察失败停在哪一步、后面的步骤没跑。
第二段：预留的 saga 编排演示位子（见文末注释）。
"""

from sagakit import StepRunner


def main():
    print("=== 顺序步骤，中途失败即停 ===")
    calls = []

    def step_one():
        calls.append("step_one")
        print("  执行 step_one")
        return "one"

    def step_two():
        calls.append("step_two")
        print("  执行 step_two")
        return "two"

    def step_three():
        calls.append("step_three")
        print("  执行 step_three")
        raise RuntimeError("step_three 失败")

    def step_four():
        calls.append("step_four")
        print("  执行 step_four")
        return "four"

    runner = StepRunner([step_one, step_two, step_three, step_four])
    try:
        runner.run()
    except RuntimeError as exc:
        print("  抛出:", exc)
    print("  实际被调用的步骤:", calls)
    print("  结论: 失败即整体停止，已成功的前序步骤没有任何回退")

    # TODO(saga 改造): saga 编排器就位后在这里补一轮演示：
    # 用注入时钟与固定种子跑一个带补偿、重试与超时的 saga，
    # 让某一步失败触发前序步骤按逆序补偿，并在重试用尽后打印
    # 补偿调用顺序、各步重试次数与最终状态，便于看清整条回退链路。


if __name__ == "__main__":
    main()
