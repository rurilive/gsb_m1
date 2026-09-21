"""colpage 现状演示：写一份小列文件，再顺序读、按行号读、按列过滤。

编码与页结构落地后的演示位子见文末注释。
"""

import json
import os
import struct
import tempfile

from colpage.errors import BadPageError
from colpage.reader import ColumnFile
from colpage.schema import Schema
from colpage.store import MAGIC, write_file


def sample_rows(count=12):
    """城市低基数、id 递增的一小批埋点数据。"""
    cities = ["北京", "上海", "广州", "北京"]
    return [{"id": 1000 + index, "city": cities[index % len(cities)],
             "amount": (index % 5) - 2}
            for index in range(count)]


def main():
    schema = Schema([("id", "int"), ("city", "str"), ("amount", "int")])
    rows = sample_rows()
    workdir = tempfile.mkdtemp(prefix="colpage-demo-")
    path = os.path.join(workdir, "orders.col")

    print("=== 写入 ===")
    written = write_file(path, schema, rows)
    print("  写入 %d 行，文件 %d 字节" % (written, os.path.getsize(path)))

    reader = ColumnFile(path)
    print("=== 顺序读回 ===")
    back = reader.read_rows()
    print("  读回 %d 行，与原数据一致: %s" % (len(back), back == rows))
    print("  头两行: %s / %s" % (back[0], back[1]))

    print("=== 按行号随机读 ===")
    print("  read_row(7) -> %s" % (reader.read_row(7),))

    print("=== 按列等值过滤 ===")
    hits = reader.filter_eq("city", "北京")
    print("  city 为北京的 %d 行: id=%s" % (len(hits), [row["id"] for row in hits]))
    print("  amount 为 0 的 %d 行" % len(reader.filter_eq("amount", 0)))

    print("=== stats ===")
    print("  %s" % (reader.stats(),))

    # ---- 第三段：编码收益、min/max 跳页与坏页容错 ----
    print("=== 编码收益 ===")
    count = 200_000
    big_path = os.path.join(workdir, "big.col")
    write_file(big_path, big_schema, _limited_rows(count))
    raw_size = (count * 8
                + (count // len(DEMO_CITIES))
                * sum(1 + len(city.encode("utf-8")) for city in DEMO_CITIES)
                + count * 8)
    paged_size = os.path.getsize(big_path)
    print("  raw 约 %d 字节，编码后 %d 字节，压到 %.1f%%"
          % (raw_size, paged_size, 100.0 * paged_size / raw_size))

    print("=== 过滤先看页头 min/max ===")
    skipping = ColumnFile(big_path)
    skipping.filter_eq("city", "00_查无此城")
    print("  查不到的城市：skipped_pages=%d, decoded_pages=%d"
          % (skipping.stats()["skipped_pages"],
             skipping.stats()["decoded_pages"]))

    print("=== 坏页：顺序读跳过，按行号读到就报错 ===")
    broken_path = os.path.join(workdir, "broken.col")
    write_file(broken_path, big_schema, _limited_rows(count))
    _break_one_page(broken_path)
    broken = ColumnFile(broken_path)
    back = broken.read_rows()
    stats = broken.stats()
    print("  顺序读回 %d/%d 行，坏页页号: %s"
          % (len(back), count, stats["bad_pages"]))
    bad_no = stats["bad_pages"][0]
    random_lookup = ColumnFile(broken_path)
    print("  好页 read_row(%d) 照常: id=%s；坏页 read_row(%d) 报错："
          % (65536, random_lookup.read_row(65536)["id"],
             bad_no * 65536), end="")
    try:
        random_lookup.read_row(bad_no * 65536)
    except BadPageError as exc:
        print(type(exc).__name__)


big_schema = Schema([("id", "int"), ("city", "str"), ("amount", "int")])
DEMO_CITIES = ["北京", "上海", "广州", "深圳"]


def _limited_rows(count):
    for index in range(count):
        yield {"id": 10_000 + index, "city": DEMO_CITIES[index % 4],
               "amount": (index % 7) - 3}


def _break_one_page(path):
    """从 footer 拿到第 1 列第 0 页的 payload，翻中间一个字节。"""
    with open(path, "rb") as handle:
        data = bytearray(handle.read())
    footer_size = struct.unpack("<I", bytes(data[-4:]))[0]
    footer = json.loads(data[len(data) - 4 - footer_size:
                            len(data) - 4].decode("utf-8"))
    column = footer["columns"][1]
    page_offset, page_length, _ = column["pages"][0]
    page_start = len(MAGIC) + column["offset"] + page_offset
    target = page_start + max(page_length - 8, 2)
    data[target] ^= 0xFF
    with open(path, "wb") as handle:
        handle.write(data)


if __name__ == "__main__":
    main()
