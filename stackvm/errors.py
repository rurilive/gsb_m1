"""VM 异常体系。"""


class VmError(Exception):
    """虚拟机运行期错误基类（汇编、解码、执行共用）。"""


class CallOverflow(VmError):
    """调用栈深度超过 VM 的 max_call_depth 上限。"""
