# httpparse

内部网关的 HTTP/1.1 请求解析：请求行 + 头部 + Content-Length / chunked body，一口气吃完整个请求再返回。2018 年上线，纯标准库，无外部依赖。

## 对外 API（不可变更）

- `parse_request(data: bytes) -> HttpRequest`
- `HttpRequest`：属性 `method` / `target` / `version`（str）、`headers`（`[(name, value)]`，原始大小写、出现顺序）、`body`（bytes）；方法 `header(name, default=None)`（大小写不敏感，取第一个匹配）
- `ParseError(ValueError)`：请求不合法时抛出

## 契约口径（历史形成，全部要保住）

- 行结束符 `\r\n` 与裸 `\n` 都认；行长度上限按含换行符的整行字节数算，8192
- obs-fold 折行头续上一条的值；头名字不做字符校验（带空格照收）；值里控制字符非法（tab 除外）
- 没有 CL/TE 时 body 为空，头部后的剩余字节忽略；TE chunked 优先于 CL；trailer 收下但不进 headers
- method 只收大写字母和连字符；version 须为 `HTTP/主.次` 数字
- 全部错误文本以 `tests/test_http.py` 为准（下游日志采集在正则匹配）

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- `constants.py`：口径常量层，行上限 8192、CR/LF、空白与分隔字节、头名键名全部收在这里，不再有魔法数。
- `tokenizer.py`：切字节层，`LineTokenizer` 维护内部缓冲，数据可分任意段 `feed`；只负责按行切、剥 CRLF/裸 LF、行长在此层拦截，不认识 HTTP。
- `message.py`：消息组装层，`RequestReader` 是显式状态机：请求行 → 头部 → 决定 body（Content-Length / chunked / 无）→ body。
- 状态推进在 `message.py` 的 `_pump()`：每个状态一个 handler，数据不够就保留状态停下返回，新数据到达后从断点继续。
- `errors.py` 放 `ParseError`；`parser.py` 只剩兼容门面，`parse_request` 把整段字节一次喂给同一个 `RequestReader` 再 `finish()` 收尾。
- 接得住流式的原因：所有解析状态（含 chunk 已收字节、trailer 区）都挂在 reader 上，`feed` 只推进不重置；`finish` 统一处理 EOF（trailer 容忍 EOF，其余残缺报历史文案）。
- 对外 API、错误类型与文本、行长口径全部不变；`tests/` 未改动，36 个测试原样全绿，`demo.py` 输出逐字节一致。
