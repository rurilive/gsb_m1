"""解析过程中抛出的异常。"""


class ParseError(Exception):
    """输入流不合 multipart/form-data 的规范。"""
