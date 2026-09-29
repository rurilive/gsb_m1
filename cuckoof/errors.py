"""cuckoof 自有异常类型。"""


class CuckooError(Exception):
    """cuckoof 各类运行期错误的基类。"""


class CapacityError(CuckooError, ValueError):
    """过滤器容量吃满或踢出超限，没法再接纳新键。"""
