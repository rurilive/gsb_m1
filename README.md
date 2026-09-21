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
reader.stats()                      # rows / columns / file_bytes
```

## 写入端

- `ColumnStore(path, schema)`：`append(row)` 收行，`close()` 落盘，可当上下文管理器
- `write_file(path, schema, rows)`：一口气写完，返回行数
- 行的键就是列名，列类型是 int（64 位有符号）与 str；行不合格抛 `SchemaError`

## 文件格式（format 1）

- 偏移 0：魔数 `colpage1`，8 字节
- 偏移 8 起：各列的数据段，一列一段首尾相接，列序与 schema 一致
- 末尾 4 字节：footer 的字节数，小端 uint32
- 再往前：footer，UTF-8 的 JSON

footer 形如：

```json
{"format": 1, "rows": 2,
 "columns": [{"name": "id", "kind": "int", "codec": "raw",
              "offset": 0, "length": 16}]}
```

`offset` 是相对正文起点的段偏移。列段编码现在只有 `raw`：int 是逐值 8 字节
小端，str 是长度 varint 加 UTF-8 字节。结构不对或内容解不开抛 `FormatError`。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 约束

纯标准库；`tests/` 里的行为与 `ColumnStore`、`ColumnFile` 的对外接口是基线，
改动时不许破坏。
