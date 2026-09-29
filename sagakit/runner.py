"""最朴素的顺序步骤执行器，纯标准库。

现状能力（基线）：

- StepRunner 接受一个步骤列表，每个步骤是任意可调用对象；
- run 按列表顺序依次调用，返回值收集成列表返回；
- 任一步骤抛出异常，整体立刻停止，异常向上抛出，后续步骤不再执行；
- 没有补偿、没有重试、没有超时、没有持久化。

这是 saga 编排器改造前的起点，基线测试锁住这里的行为。
"""


class StepRunner:
    """按顺序执行步骤列表，一步失败就整体停止。"""

    def __init__(self, steps):
        self.steps = list(steps)

    def run(self):
        """顺序执行所有步骤，返回各步返回值组成的列表。

        中途任一步抛异常，异常直接向上抛，已跑过的步骤不做任何回退。
        """
        results = []
        for step in self.steps:
            results.append(step())
        return results

    def __len__(self):
        return len(self.steps)
