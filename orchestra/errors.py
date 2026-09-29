"""orchestra 的异常体系。

所有编排相关错误都继承 OrchestraError，调用方可以只捕获基类。
"""


class OrchestraError(Exception):
    """编排错误的基类。"""


class StepNotFound(OrchestraError):
    """引用了未登记的步骤。"""


class DuplicateStep(OrchestraError):
    """步骤名重复登记。"""


class InvalidStepName(OrchestraError):
    """步骤名不是非空字符串。"""


class DefinitionError(OrchestraError):
    """流程定义不合法，如无起点、起点不是唯一、步骤不可达等。"""


class CycleError(OrchestraError):
    """流程图中存在环路，无法确定执行顺序。

    异常的 nodes 属性按字典序给出环上的全部步骤名。
    """

    def __init__(self, nodes, message=None):
        self.nodes = tuple(sorted(nodes))
        if message is None:
            message = "流程图中存在环路: %s" % (", ".join(self.nodes),)
        super().__init__(message)


class StepFailed(OrchestraError):
    """步骤执行体抛出的异常包装。

    保留原异常对象在 cause 属性里，便于上层区分业务失败与技术失败。
    """

    def __init__(self, step, cause):
        self.step = step
        self.cause = cause
        super().__init__("步骤 %r 执行失败: %s" % (step, cause))


class StepTimeout(OrchestraError):
    """步骤执行超过声明的超时上限。"""

    def __init__(self, step, limit):
        self.step = step
        self.limit = limit
        super().__init__("步骤 %r 执行超过超时上限 %s" % (step, limit))


class StateError(OrchestraError):
    """非法的步骤状态转移。"""


class RunError(OrchestraError):
    """在不可运行的状态下调用了执行入口。"""