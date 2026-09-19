"""备份工具打包一个小目录的样子（线上演示脚本，输出格式别动）。"""

import binascii
import os
import tempfile

from archlite import (
    ArchiveEntry,
    find_entry,
    pack_bytes,
    read_archive,
    unpack_bytes,
    write_archive,
)

FILES = [
    ArchiveEntry("etc/gateway.ini", b"port = 8080\n"),
    ArchiveEntry("etc/empty.marker", b""),
    ArchiveEntry("blob/rand.bin", bytes(range(256)) * 2),
]

blob = pack_bytes(FILES)
print("packed:", len(blob), "bytes")
print("header0:", binascii.hexlify(blob[:80]).decode())
back = unpack_bytes(blob)
print("entries:", [(e.name, len(e.data)) for e in back])
print("roundtrip:", pack_bytes(back) == blob)

with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "backup.al")
    write_archive(p, FILES)
    print("file roundtrip:", read_archive(p) == FILES)

print("find:", find_entry(blob, "etc/empty.marker"))
print("find missing:", find_entry(blob, "no/such"))

bad = blob[:76] + bytes([blob[76] ^ 0xFF]) + blob[77:]
try:
    unpack_bytes(bad)
except ValueError as e:
    print("corrupt:", e)
