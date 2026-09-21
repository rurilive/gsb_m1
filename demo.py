"""tstore 演示。

第一段：老裸存文件的追加与读取。
第二段：压缩块的压缩率、只解一块的随机访问、坏块跳过与老文件兼容。
"""

import random
import os
import struct
import tempfile

from tstore import TsStore
from tstore.blocks import BLOCK_HEADER, FILE_HEADER
from tstore.layout import HEADER as RAW_MAGIC


def _jittered_series(n):
    rng = random.Random(7)
    pairs = []
    ts = 1_700_000_000
    value = 20.00
    for _ in range(n):
        ts += 1000 + rng.randint(-50, 50)
        if rng.random() < 1 / 40:
            value = round(value + rng.choice([0.25, -0.25, 0.5, 0.75]), 2)
        pairs.append((ts, value))
    return pairs


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "demo.ts")
        with TsStore(path) as store:
            store.append(1700000000, 20.0)
            store.append_many(
                [(1700000001, 20.0), (1700000001, 20.25), (1700000004, 20.25)]
            )
            print("=== 追加后顺序读出 ===")
            for i, (ts, value) in enumerate(store):
                print("  #%d ts=%d value=%.2f" % (i, ts, value))

            print("=== 随机访问与定位 ===")
            print("  read_at(2) ->", store.read_at(2))
            print("  read_at(-1) ->", store.read_at(-1))
            print("  find(1700000001) ->", store.find(1700000001))
            print("  find(1700000003) ->", store.find(1700000003))

            st = store.stats()
            print("  记录数=%d 追加次数=%d 读取次数=%d" % (
                st["records"], st["appends"], st["reads"]))

        print("  文件字节数=%d" % os.path.getsize(path))

        print("=== 块压缩：一万条等间隔带抖动 ===")
        block_path = os.path.join(tmp, "demo.blk")
        pairs = _jittered_series(10_000)
        with TsStore(block_path, block_size=5_000) as store:
            store.append_many(pairs)
        total = os.path.getsize(block_path)
        print("  压缩后 %d 字节，平均 %.2f 字节/条（裸存要 16 字节）" % (
            total, total / len(pairs)))
        with TsStore(block_path) as store:
            store.read_at(7_654)
            store.read_at(123)
            st = store.stats()
            print("  两次随机 read_at 只解了 %d 块" % st["decoded_blocks"])
            print("  find 命中下标 %d" % store.find(pairs[5_000][0]))

            # 破坏第一块的块体（CRC 不过），重开后坏块跳过、另一块照读。
            with open(block_path, "r+b") as fh:
                fh.seek(FILE_HEADER.size + BLOCK_HEADER.size + 100)
                fh.write(b"\xff")
            store.close()
            corrupt = TsStore(block_path)
            st = corrupt.stats()
            print("  破坏一块后：可读 %d 条，bad_blocks=%d" % (
                st["records"], st["bad_blocks"]))
            corrupt.close()

        print("=== 老裸存文件：追加后格式不变、不用迁移 ===")
        legacy = os.path.join(tmp, "old.ts")
        with open(legacy, "wb") as fh:
            fh.write(RAW_MAGIC + struct.pack("<qd", 100, 1.5))
        with TsStore(legacy) as store:
            store.append(200, 9.5)
        with open(legacy, "rb") as fh:
            print("  文件头仍是 %r，长度 %d 字节" % (
                fh.read(len(RAW_MAGIC)), os.path.getsize(legacy)))


if __name__ == "__main__":
    main()
