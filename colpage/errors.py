"""colpage 的异常类型。

SchemaError: 列定义或行数据不符合模式。
FormatError: 文件不是合法的列文件，或者内容已经损坏。
BadPageError: 列段里某一页的页头或校验不过（磁盘坏页）。
"""


class SchemaError(ValueError):
    """列定义或行数据不符合模式。"""


class FormatError(ValueError):
    """文件结构不合法或已损坏，解析不下去。"""


class BadPageError(FormatError):
    """某一页的页头解不开或页尾校验不过。

    page 是这一页在列段里的页号（从 0 起）；跳过坏页顺序读时用得到。
    """

    def __init__(self, message, page=None):
        super().__init__(message)
        self.page = page
