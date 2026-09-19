"""httpparse.constants：解析器各层共用的字面量与上限。

魔法数字全部收在这：行上限、CRLF、空白字节、HTTP 前缀、头部名等。
改口径只动这一个文件。
"""

# 行长度上限：按含换行符的整行字节数算（即剥掉末尾 \n 后的字节数，含可能的 \r）
MAX_LINE_LENGTH = 8192

# 行结束
LF = b"\n"
CR = b"\r"
CRLF = b"\r\n"

# ASCII 字节
TAB = 9
SPACE = 32
COLON = b":"
SEMICOLON = b";"
DOT = b"."
DASH = b"-"

# method 合法区间：大写字母（连字符单独放行，M-SEARCH 这类）
UPPER_A = b"A"
UPPER_Z = b"Z"

# 版本前缀
HTTP_PREFIX = b"HTTP/"

# 头值两端空白（历史口径只剥空格和 tab）
OWS = b" \t"

# chunk 尺寸行上的参数分隔与空白
CHUNK_EXT_SEP = SEMICOLON
CHUNK_SIZE_STRIP = OWS

# 决定 body 读法的头部名（比较时统一小写）
CONTENT_LENGTH_HEADER = "content-length"
TRANSFER_ENCODING_HEADER = "transfer-encoding"
CHUNKED = "chunked"

# 解码用的编码
LATIN1 = "latin-1"
HEX = 16

# 行长超限报错文案（下游日志按这个正则采集）
LINE_TOO_LONG = "line too long: %d bytes"
