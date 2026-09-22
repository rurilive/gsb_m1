# jsonflow

内部数据管线用的手写 JSON 解析与序列化库。核心只依赖标准库的 `re`，
不依赖标准库 `json`（`json` 只出现在测试里做对拍）。

## 快速上手

```python
import io
import jsonflow

doc = jsonflow.loads('{"sku": "A-1", "qty": 3, "price": 19.9}')
doc["qty"].value                      # 3
jsonflow.dumps(doc)                   # '{"sku": "A-1", "qty": 3, "price": 19.9}'

with open("archive.json") as fp:
    doc = jsonflow.load(fp)           # 归档批处理用的读口
```

## 模块

- `jsonflow/lexer.py`：`Lexer` 把文本切成 `Token` 流，维护行列位置；`JsonError` 是统一的报错类型。
- `jsonflow/parser.py`：`Parser` 递归下降组对象，`loads` 是文本入口。
- `jsonflow/numbers.py`：`Num`，数字在解析结果里的包装。
- `jsonflow/encoder.py`：`Encoder` 与 `dumps`，默认分隔符、转义口径与标准库 `json` 一致。
- `jsonflow/stream.py`：`load` / `dump` 与 `ArchiveParser`，给入库批处理用的文件口子。

## 契约

- 数字在解析结果里是 `Num`：`text` 是字面量原文，`value` 是解析出来的数，
  `int()` / `float()` 取用；`Num` 之间按值比较。
- `loads` 收 `str`，也收 `bytes` / `bytearray`；`load` 收文本流或二进制流。
- `load(fp, chunk_size=65536)`、`dump(obj, fp, chunk_size=65536)` 两个口子参数保持一致。
- 解析失败一律抛 `JsonError`。
- `dumps` 的输出：数组元素用 `", "`、键值用 `": "` 分隔，非 ASCII 字符转义成 `\uXXXX`。

## 运行

```bash
python3 -m unittest discover -s tests    # 行为基线
python3 demo.py                          # 端到端演示
```

## 实现说明

- 词法用正则按记号逐个匹配，行列位置随消费字符推进。

（待补：数字语义、往返与性能口径。）
