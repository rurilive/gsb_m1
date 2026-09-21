"""snapwire 现状演示：快照、差分、整份同步与中断。

第一段：建目录、拍快照、改一个文件后再拍，打印差异清单，
        再用 sync_full 整份同步一次，打印搬运字节数。
第二段：预留的块级增量传输演示位子（见文末注释）。
"""

import os
import shutil
import tempfile

from snapwire import (
    Channel,
    ChannelBroken,
    compare_snapshots,
    hash_file,
    sync_full,
    take_snapshot,
)


def write(path, data):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def build_tree(root):
    """造一份演示用目录：一个报告文件加一个配置目录。"""
    write(os.path.join(root, "report.bin"), bytes(range(256)) * 256)
    write(os.path.join(root, "conf", "app.toml"), b"retries = 3\n")
    write(os.path.join(root, "conf", "log.toml"), b"level = \"info\"\n")


def main():
    work = tempfile.mkdtemp(prefix="snapwire-demo-")
    try:
        src = os.path.join(work, "src")
        dst = os.path.join(work, "dst")
        build_tree(src)

        print("=== 快照与差分 ===")
        before = take_snapshot(src)
        print("文件 %d 个：%s" % (len(before), ", ".join(before.paths())))

        report = os.path.join(src, "report.bin")
        with open(report, "r+b") as fh:
            fh.seek(30000)
            fh.write(b"patched")
        after = take_snapshot(src)
        for change in compare_snapshots(before, after):
            print("  %-8s %s" % (change.kind, change.path))

        print("=== 整份同步 ===")
        channel = Channel()
        moved = sync_full(report, os.path.join(dst, "report.bin"), channel)
        same = hash_file(report) == hash_file(os.path.join(dst, "report.bin"))
        print("改了一小段仍搬了 %d 字节，内容一致：%s" % (moved, same))

        print("=== 通道中断 ===")
        cut = Channel(limit=8192)
        try:
            sync_full(report, os.path.join(dst, "half.bin"), cut,
                      chunk_size=4096)
        except ChannelBroken as exc:
            half = os.path.join(dst, "half.bin")
            print("中断：%s" % exc)
            print("已搬 %d 字节，落盘 %d 字节，剩下一半没有着落"
                  % (cut.bytes_moved, os.path.getsize(half)))

        # TODO(块级增量传输): snapwire/transfer.py 落地后，在这里补一段演示：
        # 1) 只改 report.bin 里一小段，用 BlockIndex 与 Sender、Receiver
        #    同步一份新副本，打印搬运字节数并与上面 sync_full 的对比
        # 2) 换一个限流的小 Channel 中途切断，用同一个块索引接着跑完，
        #    展示建好的副本与源逐字节一致、已确认的块没有重传
        # 3) 打印块索引 stats() 里的存块数与去重省下的字节
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
