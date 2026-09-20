"""httpparse.constants：解析器的所有口径常量（历史值，勿动）。

魔法数字和裸字节字面量统一收在这层：行上限、行结束符、空白字节、
头名键名等。tokenizer 与 message 两层都从这里取值。
"""

# 行长度上限：按含换行符（LF）的整行字节数算（历史口径）
MAX_LINE_LENGTH = 8192

# 字节数值（与 bytes 下标比较用）
CR_BYTE = 0x0D
LF_BYTE = 0x0A
SPACE_BYTE = 0x20
TAB_BYTE = 0x09
UPPER_A = 0x41
UPPER_Z = 0x5A
HYPHEN_BYTE = 0x2D

# 字节序列（find / strip / 切片比较用）
CR = bytes([CR_BYTE])
LF = bytes([LF_BYTE])
CRLF = CR + LF
SPACE = bytes([SPACE_BYTE])
TAB = bytes([TAB_BYTE])
SPACES_TABS = SPACE + TAB
COLON = b":"
SEMICOLON = b";"
DOT = b"."

# 请求行 / body 描述
HTTP_PREFIX = b"HTTP/"

# 头名（小写匹配用）
CONTENT_LENGTH = "content-length"
TRANSFER_ENCODING = "transfer-encoding"
CHUNKED = "chunked"
