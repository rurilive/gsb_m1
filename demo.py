"""tstore 演示。

第一段：追加若干时间点，再按下标与按时间读出来。
第二段：块压缩效果、单块解码、坏块跳过与老文件兼容。
"""

import os
import random
import struct
import tempfile

from tstore import TsStore
from tstore.blocks import BLOCK_HEADER
from tstore.layout import HEADER as RAW_HEADER


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

        print("=== 块压缩 ===")
        rng = random.Random(42)
        pairs = []
        ts, value = 1700000000, 20.0
        for _ in range(10000):
            ts += 1000 + rng.randint(-3, 3)
            if rng.random() < 0.03:
                value = round(value + rng.choice([-0.5, -0.25, 0.25, 0.5]), 2)
            pairs.append((ts, value))
        cpath = os.path.join(tmp, "demo_blocks.ts")
        with TsStore(cpath, block_size=256) as store:
            store.append_many(pairs)
            size = os.path.getsize(cpath)
            print("  %d 条共 %d 字节，平均每条 %.2f 字节（裸存 16）"
                  % (len(pairs), size, size / len(pairs)))
            before = store.stats()["blocks_decoded"]
            print("  read_at(5000) ->", store.read_at(5000))
            print("  本次 read_at 解块数=%d"
                  % (store.stats()["blocks_decoded"] - before))
            print("  find(%d) -> %d" % (pairs[7777][0], store.find(pairs[7777][0])))

        print("=== 坏块跳过 ===")
        with open(cpath, "r+b") as fh:  # 把第一块负载弄坏
            fh.seek(len(RAW_HEADER) + BLOCK_HEADER.size)
            byte = fh.read(1)
            fh.seek(len(RAW_HEADER) + BLOCK_HEADER.size)
            fh.write(bytes([byte[0] ^ 0xFF]))
        with TsStore(cpath) as store:
            st = store.stats()
            print("  弄坏块 0 后：可读 %d 条，bad_blocks=%s"
                  % (st["records"], st["bad_blocks"]))
            print("  第一条可读 ->", store.read_at(0))

        print("=== 老文件兼容 ===")
        lpath = os.path.join(tmp, "legacy.ts")
        with open(lpath, "wb") as fh:
            fh.write(RAW_HEADER + struct.pack("<qd", 100, 1.5))
        with TsStore(lpath) as store:
            store.append(105, 2.5)
            print("  老文件追加后读出 ->", store.read_all())


if __name__ == "__main__":
    main()
