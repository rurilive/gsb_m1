"""crawlkit 自有异常类型。"""


class NotSupportedError(NotImplementedError):
    """当前过滤器后端不支持这个操作。"""
