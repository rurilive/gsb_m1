"""msglz: 消息总线上短消息的压缩库。"""

from .codec import MessageCodec
from .errors import FormatError, MsglzError

__all__ = ["MessageCodec", "MsglzError", "FormatError"]
