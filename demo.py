"""snapwire 现状演示：快照、差分、整份同步与中断。

第一段：建目录、拍快照、改一个文件后再拍，打印差异清单，
        再用 sync_full 整份同步一次，打印搬运字节数。
第二段：块级增量传输，同一文件改一小段只搬改动附近几个块，
        通道切断后用同一个块索引续传，已确认的块不重传。
"""

import os
import random
import shutil
import tempfile

from snapwire import (
    BlockIndex,
    Channel,
    ChannelBroken,
    Receiver,
    Sender,
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


def drive(sender, receiver, manifest, dst):
    """推进增量传输直到 dst 落盘；通道中断先把已送达的块收进仓。"""
    while True:
        try:
            if receiver.apply(manifest, dst):
                return
            sender.push(manifest)
        except ChannelBroken:
            try:
                receiver.apply(manifest, dst)
            except ChannelBroken:
                pass
            raise


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

        print("=== 块级增量传输 ===")
        big = os.path.join(src, "big.bin")
        write(big, random.Random(2024).randbytes(1 << 16))
        block = 4096
        s, r = BlockIndex(block), BlockIndex(block)

        wire = Channel()
        sender, receiver = Sender(s, wire), Receiver(r, wire)
        replica = os.path.join(dst, "big.bin")
        manifest = sender.plan(big)
        drive(sender, receiver, manifest, replica)
        print("首趟搬 %d 字节（整份 %d 字节），仓里 %s"
              % (wire.bytes_moved, os.path.getsize(big), r.stats()))

        with open(big, "r+b") as fh:
            fh.seek(40000)
            fh.write(b"tiny-edit")
        before = wire.bytes_moved
        manifest = sender.plan(big)
        drive(sender, receiver, manifest, replica)
        print("改 9 字节只搬 %d 字节（sync_full 要搬 %d），一致：%s"
              % (wire.bytes_moved - before, os.path.getsize(big),
                 hash_file(big) == hash_file(replica)))

        print("=== 增量传输中断续传 ===")
        r2 = BlockIndex(block)
        cut2 = Channel(limit=12000)
        sender2, receiver2 = Sender(s, cut2), Receiver(r2, cut2)
        resume = os.path.join(dst, "big-resume.bin")
        try:
            drive(sender2, receiver2, manifest, resume)
        except ChannelBroken as exc:
            print("中断：%s" % exc)
        print("已确认 %d 块入仓，dst 尚未落盘：%s"
              % (r2.stats()["blocks"], not os.path.exists(resume)))
        again = Channel()
        sender3, receiver3 = Sender(s, again), Receiver(r2, again)
        drive(sender3, receiver3, manifest, resume)
        print("重跑只搬 %d 字节补齐，逐字节一致：%s"
              % (again.bytes_moved, hash_file(big) == hash_file(resume)))

        wire3 = Channel()
        sender4, receiver4 = Sender(s, wire3), Receiver(r2, wire3)
        m_report = sender4.plan(report)
        drive(sender4, receiver4, m_report, os.path.join(dst, "report-x.bin"))
        print("周期内容整份 %d 字节只搬 %d 字节，块仓去重后 %s"
              % (os.path.getsize(report), wire3.bytes_moved, r2.stats()))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
