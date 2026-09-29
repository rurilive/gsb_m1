"""routez 当前实现：朴素线性匹配的前缀路由表。

现在只有逐条路径比较的能力：注册进来的模式一律按字面路径对待，
匹配时把请求路径切成段，和每条已注册模式逐段相等比较，第一条全
相等的就算命中。冒号参数、星号通配、优先级这些概念一概没有，
所有模式都只是普通静态路径。
"""

from collections import namedtuple

# 命中结果：handler 是注册时挂的处理体，params 是提取到的参数。
Match = namedtuple("Match", ["handler", "params"])


def split_path(path):
    """把路径切成段。

    约定以斜杠开头，去掉开头那个斜杠后按斜杠切分。根路径切成空列表。
    空串、不以斜杠开头、以及切出空段的路径都判为非法，直接抛错。
    """
    if not isinstance(path, str):
        raise TypeError("path 必须是字符串")
    if not path.startswith("/"):
        raise ValueError("path 必须以斜杠开头: %r" % (path,))
    if path == "/":
        return []
    segments = path[1:].split("/")
    for seg in segments:
        if seg == "":
            raise ValueError("path 里存在空段: %r" % (path,))
    return segments


class Router:
    """朴素线性路由表。

    内部只维护一个按注册顺序排列的列表，匹配时顺序扫描。
    """

    def __init__(self):
        self._routes = []  # [(path, handler), ...] 注册顺序
        self._index = {}  # path -> handler，用于查重与快速注销

    def add(self, path, handler):
        """注册一条路由。同一路径重复注册直接报错，口径明确。"""
        split_path(path)
        if path in self._index:
            raise ValueError("路径已注册: %r" % (path,))
        self._routes.append((path, handler))
        self._index[path] = handler

    def remove(self, path):
        """注销一条路由。路径没注册过则报错。"""
        if path not in self._index:
            raise KeyError(path)
        del self._index[path]
        self._routes = [(p, h) for (p, h) in self._routes if p != path]

    def match(self, path):
        """按注册顺序逐条比较，第一条逐段全等的命中，否则 None。"""
        want = split_path(path)
        for route_path, handler in self._routes:
            if split_path(route_path) == want:
                return Match(handler, {})
        return None

    def routes(self):
        """列出全部已注册路径，按注册顺序。"""
        return [p for (p, _h) in self._routes]
