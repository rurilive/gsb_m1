"""bloomchain 自有异常类型。"""


class BloomError(ValueError):
    """参数非法或容量吃满，bloomchain 各类错误的基类。"""


class CapacityError(BloomError):
    """单层写满且不允许再扩展时抛出的容量错误。"""
