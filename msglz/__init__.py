"""msglz: 消息总线上短消息的压缩库。"""

from .codec import MessageCodec
from .dict import DictStore, train_dictionary
from .errors import DictVersionError, FormatError, MsglzError

__all__ = [
    "MessageCodec",
    "DictStore",
    "train_dictionary",
    "MsglzError",
    "FormatError",
    "DictVersionError",
]
