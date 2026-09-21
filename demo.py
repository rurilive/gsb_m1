"""tstore 现状演示。

第一段：追加若干时间点，再按下标与按时间读出来。
第二段：预留的块编码与随机访问演示位子（见文末注释）。
"""

import os
import tempfile

from tstore import TsStore


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

        # TODO(块编码改造): 压缩块落地后，在这里加一段演示：
        # 同一批数据压缩后平均每条占多少字节、read_at 只解一块的效果
        # （看 stats 里解码块数的计数），再加坏块跳过与老文件兼容。
        print("  文件字节数=%d" % os.path.getsize(path))


if __name__ == "__main__":
    main()
