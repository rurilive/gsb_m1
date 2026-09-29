"""或可选的薄封装：把一串具名调用体用 Runner 串起来。

Pipeline 只是 Runner 的便捷壳，不引入任何新语义；编排器的分支、并行、
补偿等能力不在这里，而在 orchestra 的新模块里。
"""

from .runner import Runner


class Pipeline:
    """按名字顺序串联的调用体集合。"""

    def __init__(self, steps=()):
        self._runner = Runner()
        for name, func in steps:
            self._runner.add_step(name, func)

    def add(self, name, func):
        self._runner.add_step(name, func)
        return self

    def names(self):
        return self._runner.steps()

    def run(self, context=None):
        return self._runner.execute(context)

    @property
    def executed(self):
        return self._runner.executed

    def __len__(self):
        return len(self._runner.steps())

    def __repr__(self):
        return "<Pipeline steps=%d>" % (len(self),)