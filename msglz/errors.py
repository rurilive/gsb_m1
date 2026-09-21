"""msglz 的异常类型。"""


class MsglzError(Exception):
    """本包所有异常的基类。"""


class FormatError(MsglzError):
    """压缩流或帧结构不符合格式。

    帧被截断、魔数不对、校验和对不上、token 越界，都归到这里。
    """


class DictVersionError(MsglzError):
    """帧要的字典版本手里没有：要么没训过，要么已被淘汰。

    version 属性带着帧头里那个版本号。
    """

    def __init__(self, version):
        self.version = version
        super().__init__("字典版本 %d 不存在或已淘汰" % version)
