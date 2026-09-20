"""wirepack 现状演示。

第一段：把几条记录编成字节，看 16 字节定长格式长什么样。
第二段：按奇形怪状的块喂给 RecordStream，验证跨块记录照样解出来。
第三段：量一下定长记录的解码吞吐，作为线上容量的底数。
第四段：流尾被截断时解码器怎么报错。
"""

import time

from wirepack.errors import DecodeError
from wirepack.records import RECORD_SIZE, Record, pack_record
from wirepack.stream import RecordStream, chunked


def sample_records():
    return [
        Record(120001, "data", "n1"),
        Record(120002, "data", "n2", flags=1),
        Record(120003, "ack", ""),
        Record(120004, "ctrl", "node-7", flags=8),
    ]


def show_layout():
    print("=== 定长记录布局（%d 字节） ===" % RECORD_SIZE)
    for record in sample_records():
        raw = pack_record(record)
        print("  %-38s %s" % (record, raw.hex(" ")))


def show_feed():
    print("=== 按块喂入 ===")
    blob = b"".join(pack_record(r) for r in sample_records())
    for size in (3, 5, 16, 40):
        stream = RecordStream()
        seen = []
        for piece in chunked(blob, size):
            seen.extend(stream.feed(piece))
        print("  每块 %-3d 字节: 解出 %d 条, pending=%d"
              % (size, len(seen), stream.pending))
    stream = RecordStream()
    print("  尾块只喂 9 字节: 解出 %d 条, pending=%d"
          % (len(stream.feed(blob[:len(blob) - 9])), stream.pending))


def show_throughput(count=200000):
    print("=== 解码吞吐 ===")
    record = Record(123456, "data", "n1")
    raw = pack_record(record)
    blob = raw * count
    start = time.perf_counter()
    stream = RecordStream()
    decoded = stream.feed(blob)
    spent = time.perf_counter() - start
    print("  %d 条定长记录 %.3f 秒，约 %.0f 条/秒"
          % (len(decoded), spent, count / spent))


def show_truncated_tail():
    print("=== 流尾截断 ===")
    stream = RecordStream()
    stream.feed(pack_record(sample_records()[0]) + b"\x00\x01\x02")
    try:
        stream.finish()
    except DecodeError as exc:
        print("  解码器报错: %s" % (exc,))


def main():
    show_layout()
    show_feed()
    show_throughput()
    show_truncated_tail()


if __name__ == "__main__":
    main()
