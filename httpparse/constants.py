"""解析用的常量：长度上限、行结束符和各处的字节/整数字面量。

重构前这些数（8192、13、32、9 之类）散在 parse_request 各处，统一收在这里。
"""

# 行长度上限：按含换行符的整行字节数算（历史口径）
MAX_LINE_LENGTH = 8192

# 行结束符：\r\n 与裸 \n 都认（历史容错）
CR = 13
LF = 10
CRLF = b"\r\n"

# 空白：空格、tab
SPACE = 32
TAB = 9
WHITESPACE = b" \t"

# 请求行/头部的分隔字面量
HTTP_PREFIX = b"HTTP/"
DOT = b"."
COLON = b":"
SEMICOLON = b";"
DASH = b"-"

# method 只收大写字母和连字符（M-SEARCH 这类）
METHOD_A = ord("A")
METHOD_Z = ord("Z")
METHOD_DASH = ord("-")

# 头部相关头名（小写比较用）
CONTENT_LENGTH = "content-length"
TRANSFER_ENCODING = "transfer-encoding"
CHUNKED = "chunked"

# 文本解码
LATIN1 = "latin-1"
