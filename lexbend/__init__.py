"""lexbend: 公式编辑器用的表达式词法层。

全文扫描出带行列位置的 token 序列，配一个掂着文本的编辑缓冲。
纯标准库，无外部依赖。
"""

from lexbend.buffer import BufferError, TextBuffer
from lexbend.scanner import Cursor, iter_tokens, scan
from lexbend.token import (
    COMMENT,
    EOF,
    ERROR,
    IDENT,
    KINDS,
    NUMBER,
    OP,
    STRING,
    Token,
    keys,
)

__all__ = [
    "BufferError",
    "COMMENT",
    "Cursor",
    "EOF",
    "ERROR",
    "IDENT",
    "KINDS",
    "NUMBER",
    "OP",
    "STRING",
    "TextBuffer",
    "Token",
    "iter_tokens",
    "keys",
    "scan",
]
