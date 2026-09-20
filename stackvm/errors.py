"""VM 异常体系。"""


class VmError(Exception):
    """虚拟机运行期错误基类（汇编、解码、执行共用）。"""
