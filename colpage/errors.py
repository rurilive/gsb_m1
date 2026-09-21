"""colpage 的异常类型。

SchemaError: 列定义或行数据不符合模式。
FormatError: 文件不是合法的列文件，或者内容已经损坏。
"""


class SchemaError(ValueError):
    """列定义或行数据不符合模式。"""


class FormatError(ValueError):
    """文件结构不合法或已损坏，解析不下去。"""
