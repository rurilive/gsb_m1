"""网关收请求并解析的样子（线上 demo，输出格式别动）。"""

from httpparse import parse_request

S1 = (
    b"GET /index.html?a=1 HTTP/1.1\r\n"
    b"Host: example.com\r\n"
    b"X-Trace: abc123\r\n"
    b"Accept: */*\r\n"
    b"\r\n"
)

S2 = (
    b"POST /api/items HTTP/1.1\r\n"
    b"Content-Type: application/json\r\n"
    b"Content-Length: 7\r\n"
    b"\r\n"
    b'{"a":1}'
)

S3 = (
    b"PUT /upload HTTP/1.1\r\n"
    b"Transfer-Encoding: chunked\r\n"
    b"X-Flow: f-9\r\n"
    b"\r\n"
    b"9\r\npart-one|\r\n"
    b"9;flow=f-9\r\npart-two|\r\n"
    b"0\r\nX-Crc: ok\r\n"
    b"\r\n"
)

S4 = (
    b"GET /folded HTTP/1.1\r\n"
    b"X-Desc: first\r\n"
    b"\tsecond\r\n"
    b"  third\r\n"
    b"\r\n"
)

R1 = parse_request(S1)
print("== sample 1: GET ==")
print("method=%s target=%s version=%s" % (R1.method, R1.target, R1.version))
print("headers=%r" % (R1.headers,))
print("header('x-trace')=%r" % (R1.header("x-trace"),))
print("header('missing')=%r" % (R1.header("missing"),))
print("body=%r" % (R1.body,))

R2 = parse_request(S2)
print("== sample 2: POST (Content-Length) ==")
print("method=%s target=%s" % (R2.method, R2.target))
print("content_length_header=%r" % (R2.header("content-length"),))
print("body=%r" % (R2.body,))

R3 = parse_request(S3)
print("== sample 3: chunked upload ==")
print("method=%s" % (R3.method,))
print("flow=%r" % (R3.header("x-flow"),))
print("body=%r" % (R3.body,))

R4 = parse_request(S4)
print("== sample 4: folded header ==")
print("x-desc=%r" % (R4.header("x-desc"),))
