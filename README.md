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

## 修复说明

- 分隔行候选要看到后面两个字节才算数:跟的是 CRLF 或 `--` 才是真
  分隔行,正文里长得像的字节(含半截前缀)原样写进正文,不再被
  切开;候选跨块时先留在手里,等字节到齐再判,不再按猜测跳字节
- 分隔行或收尾的 `--` 恰好被切在块边界时,缓存候选等下一块拼齐,
  收尾分隔行被切开不再丢最后一段
- `finish()` 时还没看到收尾分隔行就抛 `ParseError`,半路断掉的流
  不再当成功
- 头部块跨块时统一按 `\r\n\r\n` 找结束空行,修掉头部值尾随多出的
  回车
- Content-Disposition 参数的引号值支持反斜杠转义,
  `filename="a\"b.txt"` 这类值能完整解出,与 reference 语义一致
- 新增 `tests/test_randomized.py`(随机切块与 reference 对拍、断流
  报错)和 `tests/test_stress.py`(50MB 正文,峰值内存 8MB 内、
  十秒内跑完)
