"""colpage: 把行记录按列拆开、顺序写本地文件的列存库。

写入端 ColumnStore 收行落盘，读取端 ColumnFile 顺序读回、按行号取行、
按列等值过滤；列段编码现在只有不压缩的 raw。
"""

from colpage.codec import RAW, decode_segment, encode_segment
from colpage.errors import FormatError, SchemaError
from colpage.reader import ColumnFile
from colpage.schema import Schema
from colpage.store import MAGIC, ColumnStore, write_file

__all__ = [
    "ColumnFile",
    "ColumnStore",
    "FormatError",
    "MAGIC",
    "RAW",
    "Schema",
    "SchemaError",
    "decode_segment",
    "encode_segment",
    "write_file",
]
