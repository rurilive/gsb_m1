# chunkmime

按块喂入的 multipart/form-data 解析器,纯标准库,无外部依赖。

## 用法

上传网关收到多少字节就往后端喂多少,解析器边收边把字段和文件内容
交出去:

```python
from chunkmime import MultipartParser, PartCollector

collector = PartCollector()
parser = MultipartParser(boundary, collector)
for chunk in chunks:
    parser.feed(chunk)
parser.finish()
for part in collector.parts():
    print(part.name, part.filename, len(part.data))
```

- `MultipartParser(boundary, sink=None)`:boundary 是 Content-Type 里的
  边界串,str 或 bytes 都行。`feed(chunk)` 喂任意大小的块,`finish()`
  在流结束后收尾
- sink 是结果的接收端,要有 `begin_part(headers, params)`、`write(data)`、
  `end_part()` 三个方法:
  - `PartCollector`:把正文收进内存,`parts()` 取 `Part` 列表
  - `DiscardSink`:只记账(部分数、字节数、字段名),大文件或压测时用
- `Part` 上有 `headers`、`params`、`data`,还有 `name` 和 `filename`
  两个快捷属性,取自 Content-Disposition 的参数

## 语义约定

- 分隔行按 CRLF 换行;收尾分隔行之后的 epilogue 忽略,第一个分隔行
  之前的 preamble 也忽略
- 正文不包含分隔行前那个 CRLF,也不包含部分头部后面的结束空行
- 正文里出现和分隔行长得像的字节时,按规范那一截不算分隔行
- `chunkmime/reference.py` 的 `parse_all(body, boundary)` 把整份 body
  一次切完,是语义基准,给测试对拍用;增量实现切出来的东西要和它
  一致,结构不完整的输入两边都要报 `ParseError`

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
