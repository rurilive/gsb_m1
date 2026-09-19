# cookiest

网关进程内共享的 Cookie 罐：上游 Set-Cookie 解析、按请求匹配、重启恢复。多线程共用一个实例，纯标准库，无外部依赖。

## 模块

- `cookiest/cookie.py`：`Cookie` 值对象、`parse_set_cookie` / `parse_expires`
- `cookiest/jar.py`：`CookieJar`——add / set_cookie / match_for(url) / remove / snapshot，clock 可注入
- `cookiest/serial.py`：dump / load（JSON）

## 运行

```bash
python3 demo.py
```

## Known Issues
