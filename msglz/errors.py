"""msglz 的异常类型。"""


class MsglzError(Exception):
    """本包所有异常的基类。"""


class FormatError(MsglzError):
    """压缩流或帧结构不符合格式。

    帧被截断、魔数不对、校验和对不上、token 越界，都归到这里。
    """


class DictVersionError(MsglzError):
    """帧头要的字典版本本地没有。

    版本号从未存在、已经被淘汰、或调用方没接 DictStore 却收到带
    字典的帧，都归到这里。异常里带着帧声称的版本号，绝不拿别的
    字典硬解——硬解只能吐垃圾。
    """

    def __init__(self, version, message=None):
        self.version = version
        if message is None:
            message = "字典版本 %s 不可用" % (version,)
        super().__init__(message)
