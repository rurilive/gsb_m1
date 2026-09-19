"""confy 的异常类型。"""


class MissingKeyError(KeyError):
    """访问了不存在的配置键。"""


class ConfigError:
    """单个配置问题：key、原因、来源层（键缺失时 layer 为 None）。"""

    def __init__(self, key, reason, layer):
        self.key = key
        self.reason = reason
        self.layer = layer

    def __repr__(self):
        return (
            f"ConfigError(key={self.key!r}, reason={self.reason!r}, "
            f"layer={self.layer!r})"
        )

    def __str__(self):
        return f"{self.key}: {self.reason}（层: {self.layer or '无来源'}）"


class ConfigErrors(Exception):
    """validate 汇总抛出的配置问题集合，可迭代/取长度。"""

    def __init__(self, errors):
        self.errors = list(errors)
        message = "配置校验失败:\n" + "\n".join(f"  - {e}" for e in self.errors)
        super().__init__(message)

    def __iter__(self):
        return iter(self.errors)

    def __len__(self):
        return len(self.errors)
