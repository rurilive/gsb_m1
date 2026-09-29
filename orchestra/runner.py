"""朴素顺序 runner：现有能力，行为被 tests/test_runner.py 锁死。

Runner 维护一张步骤名到执行体的映射，以及一个显式的先后顺序列表。
execute 严格按登记顺序串行调用执行体，遇到异常立刻停下并把异常向上抛，
已经执行过的步骤记在 executed 里供调用方查看。
"""

from .errors import (
    DuplicateStep,
    InvalidStepName,
    OrchestraError,
    StepNotFound,
)


class Runner:
    """顺序执行步骤列表的最小运行器。

    add_step(name, func) 登记步骤，func 是接收字典 context 并返回任意值的
    可调用对象；execute(context=None) 按登记顺序逐个调用。
    """

    def __init__(self):
        self._order = []
        self._steps = {}
        self._executed = []

    def add_step(self, name, func):
        """登记一个步骤，步骤名须是非空字符串且不与已有步骤重名。"""
        if not isinstance(name, str) or not name:
            raise InvalidStepName("步骤名必须是非空字符串: %r" % (name,))
        if name in self._steps:
            raise DuplicateStep("步骤重复登记: %r" % (name,))
        if not callable(func):
            raise OrchestraError("步骤执行体必须可调用: %r" % (func,))
        self._order.append(name)
        self._steps[name] = func
        return self

    def steps(self):
        """已登记步骤名，按登记先后返回。"""
        return list(self._order)

    @property
    def executed(self):
        """按登记顺序执行成功的步骤名副本。"""
        return list(self._executed)

    def has_step(self, name):
        """步骤是否已登记。"""
        return name in self._steps

    def execute(self, context=None):
        """按登记顺序串行执行全部步骤，返回 context。

        任一步骤抛异常时不吞掉，直接向上传播，executed 保留此前成功的步骤。
        """
        ctx = {} if context is None else context
        self._executed = []
        for name in self._order:
            result = self._steps[name](ctx)
            self._executed.append(name)
            if isinstance(result, dict):
                ctx.update(result)
        return ctx

    def __repr__(self):
        return "<Runner steps=%d executed=%d>" % (
            len(self._order), len(self._executed))


def require_step(steps, name):
    """工具函数：在映射里取一个步骤，缺失时抛 StepNotFound。"""
    try:
        return steps[name]
    except KeyError:
        raise StepNotFound("未知步骤: %r" % (name,))