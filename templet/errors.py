"""模板异常体系。"""


class TemplateError(Exception):
    """模板错误基类。"""


class TemplateSyntaxError(TemplateError):
    """模板源码不符合语法。"""


class TemplateCycleError(TemplateError):
    """include 嵌套深度超过 Engine.max_include_depth（含直接/间接递归）。"""
