"""archlite: 内部备份工具用的 tar-lite 归档格式（512 字节块，无压缩，纯标准库）。

格式：每个条目 = 512 字节头 + 数据（补零到 512 的倍数），归档以两个全零块结尾。
头部布局与偏移常量集中在 archlite.header，本模块只是对外门面（保持历史导入路径）。

行为口径（历史形成的，全部要保住，tests/test_archlite.py 是清单）：
- 字节串归档不足 512 字节报错；归档中部/尾部不足一块的字节与结束块之后的字节一律忽略
- find_entry 扫描时遇到坏归档不抛错，返回 None（恢复工具依赖）
- 打包输出字节级确定（无时间戳等易变字段）
"""

from archlite.entry import ArchiveEntry
from archlite.header import MAGIC
from archlite.reader import find_entry, read_archive, unpack_bytes
from archlite.writer import pack_bytes, write_archive

__all__ = [
    "ArchiveEntry",
    "MAGIC",
    "pack_bytes",
    "unpack_bytes",
    "write_archive",
    "read_archive",
    "find_entry",
]
