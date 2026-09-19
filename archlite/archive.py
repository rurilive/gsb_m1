"""archlite 兼容门面：对外名字仍由本模块导出，实现已分层。

- archlite.format：块/头部布局常量与校验和（改布局只动这里）
- archlite.entry：ArchiveEntry 与写入前条目校验
- archlite.writer：头部拼装与写出（pack_bytes / write_archive）
- archlite.reader：头部解析、校验与扫描（unpack_bytes / read_archive / find_entry）

行为口径（历史形成，全部要保住，tests/test_archlite.py 是清单）：
- 归档头部不足 512 字节报错；中部/尾部不足一块的字节与结束块之后的字节一律忽略
- find_entry 扫描时遇到坏归档不抛错，返回 None（恢复工具依赖）
- 打包输出字节级确定（无时间戳等易变字段）
"""

from archlite.entry import ArchiveEntry
from archlite.format import MAGIC
from archlite.reader import find_entry, read_archive, unpack_bytes
from archlite.writer import pack_bytes, write_archive

__all__ = [
    "MAGIC",
    "ArchiveEntry",
    "pack_bytes",
    "unpack_bytes",
    "write_archive",
    "read_archive",
    "find_entry",
]
