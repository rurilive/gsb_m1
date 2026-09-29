"""bloomx 自有异常类型。"""


class NotSupportedError(NotImplementedError):
    """当前过滤器不支持这个操作。"""


class CapacityError(ValueError):
    """过滤器容量吃满或层数到顶，无法再接纳新键。"""