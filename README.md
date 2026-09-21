# colpage

把行记录按列拆开、顺序写进本地文件的列存库，纯标准库，无外部依赖。

## 用法

```python
from colpage import ColumnFile, Schema, write_file

schema = Schema([("id", "int"), ("city", "str")])
write_file("orders.col", schema, [{"id": 1, "city": "北京"}])

reader = ColumnFile("orders.col")
reader.read_rows()                  # 顺序读回整表
reader.read_row(0)                  # 按行号取一行，越界抛 IndexError
reader.filter_eq("city", "北京")    # 等值过滤，按行序返回命中的行
reader.read_column("id")            # 整列读出
reader.stats()
# rows / columns / file_bytes / decoded_pages / skipped_pages / bad_pages
```

## 写入端

- `ColumnStore(path, schema)`：`append(row)` 收行，`close()` 落盘，可当上下文管理器
- `write_file(path, schema, rows)`：一口气写完，返回行数
- 行的键就是列名，列类型是 int（64 位有符号）与 str；行不合格抛 `SchemaError`

## 文件格式（format 2）

- 偏移 0：魔数 `colpage1`，8 字节
- 偏移 8 起：各列的数据段，一列一段首尾相接，列序与 schema 一致
- 末尾 4 字节：footer 的字节数，小端 uint32
- 再往前：footer，UTF-8 的 JSON

footer 形如：

```json
{"format": 2, "rows": 2,
 "columns": [{"name": "id", "kind": "int", "codec": "paged",
              "offset": 0, "length": 37,
              "pages": [[0, 37, 2]]}]}
```

`offset` 是相对正文起点的段偏移，`pages` 是页目录，每项是
`[段内偏移, 页字节数, 页内行数]`，各列页边界一致（每 `PAGE_ROWS` 行一页，
末页可短）。

列段 `codec=paged` 时由首尾相接的页组成，一页一种编码，页框架（小端）：

```
[uvarint 头长][页头][payload][uint32 CRC32]
```

CRC32 覆盖「头长前缀 + 页头 + payload」。页头依次是：

- `enc`：1 字节编码号
- `nrows`：uvarint，页内行数（页自描述，不依赖写端页大小）
- `payload_len`：uvarint
- min / max：int 用两个 zigzag svarint；str 用「uvarint 长度 + UTF-8」各一

payload 编码按 `enc` 分发：

- int `0` 帧参照 + 增量：首项是本页基准（首值绝对值），其余是页内相邻值
  差的 zigzag varint；任何一页都能单独解，按行号读只解目标页
- int `1` raw 兜底：逐值 8 字节小端（增量不划算时自动选它）
- str `2` 字典 + 逐值 code：`字典 + 每个值一个 uvarint code`
- str `3` 字典 + 游程：`字典 + [uvarint 总条数, (code, run_len)...]`
- str `4` raw 兜底：逐值 `uvarint 长度 + UTF-8`

字典是 `uvarint 项数 + 每项(uvarint 长度 + UTF-8)`。写端按字符串第一次出现
的顺序给全局 code，相邻页复用同一编号；每页只带本页用到的字典项，字典扩了
老页也不受影响，任何一页都自描述、可独立解开。

读取策略：

- `read_row(i)` 用页目录定位，只解目标行所在那一页（每列各 1 页）
- `filter_eq` 先只读页头取 min/max，值不在 `[min, max]` 的页整页跳过
  （不读 payload、不校验、不计 `decoded_pages`），命中页才解码
- 顺序读碰到页头解不开或 CRC 不过的坏页：跳过该页、页号进 stats 的
  `bad_pages`；`read_row(i)` 正好落在坏页则抛 `BadPageError`，其余页照读

旧的 `format: 1`、`codec: "raw"` 文件照旧能读（int 逐值 8 字节小端，
str 为 uvarint 长度加 UTF-8），读入口不拒收。结构不对或内容解不开抛
`FormatError`。

写入端按列各留一页内存缓冲，页满即编码写进目标文件同目录的临时文件，
`close()` 时拼成正式文件，整表不会同时进内存。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 约束

纯标准库；`tests/` 里的行为与 `ColumnStore`、`ColumnFile` 的对外签名是基线，
改动时不许破坏。
