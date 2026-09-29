"""最朴素的取值器：把点号分隔的路径逐级拆开，逐层取字典键。

没有数组、通配、过滤、递归下降，也没有切片。取不到就返回 None。
"""


class Getter:
    """按点号路径在嵌套字典里取值。

    路径形如 "a.b.c"，按点号切分后逐层从字典里取键；任意一层取不到，
    或者中途遇到的对象不是字典，就返回 None。
    """

    def __init__(self, root):
        self.root = root

    def get(self, path):
        if not isinstance(path, str):
            raise TypeError("path must be a string")
        if path == "":
            return self.root
        current = self.root
        for part in path.split("."):
            if not isinstance(current, dict):
                return None
            if part not in current:
                return None
            current = current[part]
        return current
