"""vcbox 现状演示。

第一段：跑整数时钟，tick 两次看看计数怎么走；
第二段：预留的因果时钟演示位子（向量、偏序、并发判定，见文末注释）。
"""

from vcbox import Clock


def main():
    print("=== 整数时钟 ===")
    clock = Clock()
    print("  tick -> %d" % (clock.tick(),))
    print("  tick -> %d" % (clock.tick(),))
    print("  value -> %d" % (clock.value,))

    # TODO(因果时钟改造): 把 vcbox 从整数时钟扩成向量时钟与偏序之后，
    # 在这里补第二段演示：开三个进程，各自 tick 若干次并互发消息，打印
    # 各进程的向量，再挑两个向量判定严格小于、严格大于与并发三种关系，
    # 并演示两份向量的合并结果。偏序与合并的语义见 README 的目标一节
    # 与任务描述。


if __name__ == "__main__":
    main()
