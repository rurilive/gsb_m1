"""colpage: 把行记录按列拆开、分页编码写本地文件的列存库。

写入端 ColumnStore 收行落盘，读取端 ColumnFile 顺序读回、按行号取行、
按列等值过滤。列段按 N 行一页编码：低基数字符串走字典加游程，
递增整数走帧参照加增量；页头记编码与 min/max，页尾带 CRC32。
旧的 raw 整段文件（format 1）照旧能读。
"""

from colpage.errors import BadPageError
from colpage.codec import RAW, decode_segment, encode_segment
from colpage.errors import FormatError, SchemaError
from colpage.reader import ColumnFile
from colpage.schema import Schema
from colpage.store import MAGIC, PAGE_ROWS, ColumnStore, write_file

__all__ = [
    "BadPageError",
    "ColumnFile",
    "ColumnStore",
    "FormatError",
    "MAGIC",
    "PAGE_ROWS",
    "RAW",
    "Schema",
    "SchemaError",
    "decode_segment",
    "encode_segment",
    "write_file",
]
