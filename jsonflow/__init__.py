"""jsonflow：手写的 JSON 解析与序列化。

核心只用标准库的 re，不依赖标准库 json；json 只在测试里用来对拍。
"""

from .encoder import Encoder, dumps
from .lexer import JsonError, Lexer, Token
from .numbers import Num
from .parser import Parser, loads
from .stream import ArchiveParser, dump, load

__all__ = [
    "ArchiveParser",
    "Encoder",
    "JsonError",
    "Lexer",
    "Num",
    "Parser",
    "Token",
    "dump",
    "dumps",
    "load",
    "loads",
]

__version__ = "0.4.2"
