"""内存占用口径：按深遍历累加，重复引用只算一次。"""

import sys


def deep_size(obj, exclude=None):
    """对象加上它可达的容器的实际占用字节数。

    用 sys.getsizeof 逐层累加，dict 的键值、list/tuple/set 的元素、
    实例的 __dict__ 与 __slots__ 都算进去；id 相同的对象只算一次，
    共享的整数不会重复计。

    exclude 给一个对象或一串对象，它们连着各自可达的东西整个跳过，
    用来单独量某一部分的占用，比如排除记录库只看索引本体。
    """
    seen = set()
    if exclude is not None:
        if isinstance(exclude, (list, tuple, set)):
            for item in exclude:
                _mark(item, seen)
        else:
            _mark(exclude, seen)
    return _walk(obj, seen)


def human(num_bytes):
    """1048576 -> "1.00 MB"。"""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.2f %s" % (size, unit)
        size /= 1024


def _children(obj):
    """对象直接引用的下一层。"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield value
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            yield item
    else:
        if hasattr(obj, "__dict__"):
            yield obj.__dict__
        slots = getattr(type(obj), "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if hasattr(obj, name):
                yield getattr(obj, name)


def _mark(obj, seen):
    oid = id(obj)
    if oid in seen:
        return
    seen.add(oid)
    for child in _children(obj):
        _mark(child, seen)


def _walk(obj, seen):
    oid = id(obj)
    if oid in seen:
        return 0
    seen.add(oid)
    total = sys.getsizeof(obj)
    for child in _children(obj):
        total += _walk(child, seen)
    return total
