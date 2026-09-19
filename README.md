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
