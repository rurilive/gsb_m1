"""packlex 的现有实现。

这里只有一套最朴素的恒等编码：encode 把输入字节原样返回，decode 把输入
字节原样返回。没有任何压缩，输出长度永远等于输入长度；没有字典，没有
回溯引用，没有变长整数，也没有滑动窗口与分块这些概念。它唯一确定的能
力，是任意字节串 encode 再 decode 能逐字节还原。
"""


class PackError(Exception):
    """packlex 的错误基类。

    目前恒等编码不会因为数据内容报错，这个基类先立在这里，供后续把
    压缩相关异常统一收拢到一个可捕捉的类型下。
    """


class IdentityCodec:
    """朴素恒等编解码器。

    只做一件确定的事：encode 原样返回输入字节，decode 原样返回输入字节。
    输出与输入逐字节相同，故长度不变，谈不上压缩，也不会因为数据里出现
    什么内容而例外。
    """

    def __init__(self):
        """建立一个恒等编解码器，当前没有任何可配置参数。"""

    def encode(self, data):
        """把一段字节原样作为结果返回。

        data 必须是 bytes 或 bytearray，否则抛 TypeError。返回的字节与输入
        逐字节相同，长度也相同。
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes or bytearray")
        return bytes(data)

    def decode(self, data):
        """把一段字节原样作为结果返回。

        data 必须是 bytes 或 bytearray，否则抛 TypeError。对任意由 encode
        产出的数据，decode 都能逐字节还原成 encode 的输入。
        """
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes or bytearray")
        return bytes(data)
