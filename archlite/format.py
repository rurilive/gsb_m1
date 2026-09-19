"""archlite 块/头部布局的唯一定义处。

读写两层都从这里取偏移与尺寸；改头部布局（比如下版本加版本字段）只动本文件。

格式：每个条目 = 512 字节头 + 数据（补零到 BLOCK_SIZE 的倍数），
归档以两个全零块结尾。头部为大端：
0-4 魔数 MAGIC；4-68 名字（utf-8，NUL 补齐）；68-76 数据长度 u64；
76-80 校验和 u32（对校验和字段置零后的整个头部按字节求和）；80-512 全零填充。
"""

MAGIC = b"ARCL"

BLOCK_SIZE = 512
HEADER_SIZE = BLOCK_SIZE
END_BLOCKS = 2

MAGIC_OFFSET = 0
MAGIC_SIZE = 4
NAME_OFFSET = 4
NAME_SIZE = 64
SIZE_OFFSET = NAME_OFFSET + NAME_SIZE          # 68
SIZE_SIZE = 8
CHECKSUM_OFFSET = SIZE_OFFSET + SIZE_SIZE      # 76
CHECKSUM_SIZE = 4
# 80 起为全零填充，直至 HEADER_SIZE。

SIZE_FORMAT = ">Q"
CHECKSUM_FORMAT = ">I"


def header_checksum(header):
    """对校验和字段置零后的整个头部按字节求和（u32）。"""
    return (
        sum(header[:CHECKSUM_OFFSET])
        + sum(header[CHECKSUM_OFFSET + CHECKSUM_SIZE:])
    ) & 0xFFFFFFFF


def pad_length(data_len):
    """数据为补齐到整块需要追加的零字节数。"""
    return (-data_len) % BLOCK_SIZE
