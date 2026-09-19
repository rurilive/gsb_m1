"""exprx: 规则引擎内嵌的表达式求值，递归下降实现，纯标准库。

支持算术、比较、and/or、let 绑定，语言语义见 README。
"""

from .evaluator import Evaluator

__all__ = ["Evaluator", "evaluate"]


def evaluate(text, variables=None):
    """便捷入口：每次调用使用独立的求值器实例。"""
    return Evaluator().evaluate(text, variables)
