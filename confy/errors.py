"""confy 的异常类型。"""


class MissingKeyError(KeyError):
    """访问了不存在的配置键。"""


class ConfigError:
    """单条配置问题：key / 原因 / 取值所在层（缺失键的 layer 为 None）。"""

    def __init__(self, key, reason, layer):
        self.key = key
        self.reason = reason
        self.layer = layer

    def __repr__(self):
        return (
            f"ConfigError(key={self.key!r}, reason={self.reason!r}, "
            f"layer={self.layer!r})"
        )

    def __eq__(self, other):
        return (
            isinstance(other, ConfigError)
            and (self.key, self.reason, self.layer)
            == (other.key, other.reason, other.layer)
        )


class ConfigErrors(Exception):
    """validate 汇总抛出的配置问题集合，.errors 为 ConfigError 列表。"""

    def __init__(self, errors):
        self.errors = list(errors)
        summary = "; ".join(f"{e.key}: {e.reason}" for e in self.errors)
        super().__init__(f"{len(self.errors)} 个配置问题: {summary}")
