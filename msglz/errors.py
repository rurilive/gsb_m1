"""msglz 的异常类型。"""


class MsglzError(Exception):
    """本包所有异常的基类。"""


class FormatError(MsglzError):
    """压缩流或帧结构不符合格式。

    帧被截断、魔数不对、校验和对不上、token 越界，都归到这里。
    """
