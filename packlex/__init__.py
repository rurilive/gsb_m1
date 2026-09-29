"""packlex: 一个字节编解码小库，纯标准库，无外部依赖。

现阶段只有一层：IdentityCodec 把输入字节原样算作输出，decode 再把输出
原样还原回去。encode 不做任何压缩，没有字典，没有回溯引用，没有变长
整数，也没有滑动窗口的概念。它只保证一件事，就是任意字节串 encode 再
decode 能逐字节拿回来。
"""

from .codec import IdentityCodec

__all__ = ["IdentityCodec"]
