"""colpage 现状演示：写一份小列文件，再顺序读、按行号读、按列过滤。

编码与页结构落地后的演示位子见文末注释。
"""

import os
import tempfile

from colpage.reader import ColumnFile
from colpage.schema import Schema
from colpage.store import write_file


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

    # TODO(编码与页结构): 页结构与列级编码落地后，在这里补第三段演示：
    # 同一批数据换低基数与递增整数列，对比编码前后文件体积；
    # 过滤走页头 min/max 跳页，打印真解码的页数，再造一页坏数据看跳过与报错。


if __name__ == "__main__":
    main()
