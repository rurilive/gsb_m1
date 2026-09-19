"""编解码异常。"""


class CodecError(ValueError):
    """输入不符合编解码约定（非法字符、坏尾块、组值溢出等）。"""
