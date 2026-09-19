"""httpparse.parser 行为清单——重构期间一个字都不改，必须原样全绿。"""

import unittest

from httpparse import HttpRequest, ParseError, parse_request


class TestRequestLine(unittest.TestCase):
    def test_minimal_get(self):
        self.assertTrue(issubclass(ParseError, ValueError))
        r = parse_request(b"GET / HTTP/1.1\r\n\r\n")
        self.assertEqual(r.method, "GET")
        self.assertEqual(r.target, "/")
        self.assertEqual(r.version, "HTTP/1.1")
        self.assertEqual(r.headers, [])
        self.assertEqual(r.body, b"")

    def test_target_and_versions(self):
        r = parse_request(b"GET /a/b?x=1&y=2 HTTP/1.1\r\n\r\n")
        self.assertEqual(r.target, "/a/b?x=1&y=2")
        self.assertEqual(parse_request(b"GET / HTTP/1.0\r\n\r\n").version, "HTTP/1.0")
        # 历史行为：只要 HTTP/主.次 都收，不校验具体版本
        self.assertEqual(parse_request(b"GET / HTTP/9.9\r\n\r\n").version, "HTTP/9.9")

    def test_malformed_line_variants(self):
        bad_lines = [
            b"GET /\n\n",                # 只有两段
            b"GET /a b HTTP/1.1\n\n",    # 四段
            b"GET / FTP/1.1\n\n",        # 不是 HTTP/
            b"get / HTTP/1.1\n\n",       # method 小写（历史校验：只收大写字母和 -）
            b"GET / HTTP/1\n\n",         # 版本没有主.次
            b"GET / HTTP/x.1\n\n",       # 版本非数字
        ]
        for raw in bad_lines:
            with self.assertRaises(ParseError) as ctx:
                parse_request(raw)
            first = raw.split(b"\n")[0]
            self.assertEqual(str(ctx.exception), "malformed request line: %r" % first)

    def test_empty_request_raises(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"")
        self.assertEqual(str(ctx.exception), "empty request")

    def test_str_input_type_error(self):
        with self.assertRaises(TypeError):
            parse_request("GET / HTTP/1.1\r\n\r\n")

    def test_truncated_headers_variants(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"GET / HTTP/1.1\r\nHost: x")
        self.assertEqual(str(ctx.exception), "truncated headers")
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"GET / HTTP/1.1")
        self.assertEqual(str(ctx.exception), "truncated headers")

    def test_request_line_too_long(self):
        line = b"GET /" + b"a" * 9000 + b" HTTP/1.1"
        with self.assertRaises(ParseError) as ctx:
            parse_request(line + b"\r\n\r\n")
        # 历史口径：行长度按含换行符的整行字节数算
        self.assertEqual(
            str(ctx.exception), "line too long: %d bytes" % (len(line) + 1)
        )

    def test_header_line_at_8192_boundary_ok(self):
        v = b"a" * 8185  # "X-Ok: " + v + 换行 = 8192，正好在限内
        r = parse_request(b"GET / HTTP/1.1\r\nX-Ok: " + v + b"\r\n\r\n")
        self.assertEqual(r.header("x-ok"), v.decode())

    def test_header_line_over_8192_raises(self):
        v = b"a" * 8186  # 含换行 8194，超限
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"GET / HTTP/1.1\r\nX-Big: " + v + b"\r\n\r\n")
        self.assertEqual(str(ctx.exception), "line too long: 8194 bytes")


class TestHeaders(unittest.TestCase):
    def test_order_case_duplicates(self):
        r = parse_request(
            b"GET / HTTP/1.1\r\nHost: a\r\nx-lowEr: b\r\nX-A: 1\r\nX-A: 2\r\n\r\n"
        )
        self.assertEqual(
            r.headers,
            [("Host", "a"), ("x-lowEr", "b"), ("X-A", "1"), ("X-A", "2")],
        )

    def test_value_normalization(self):
        r = parse_request(
            b"GET / HTTP/1.1\r\nX-A:\t  v  \t\r\nX-B:v\r\nX-C:\r\n\r\n"
        )
        self.assertEqual(r.header("x-a"), "v")
        self.assertEqual(r.header("x-b"), "v")
        self.assertEqual(r.header("x-c"), "")

    def test_missing_colon_raises(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"GET / HTTP/1.1\r\nX-Bad\r\n\r\n")
        self.assertEqual(str(ctx.exception), "malformed header line: b'X-Bad'")

    def test_empty_name_raises(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"GET / HTTP/1.1\r\n: v\r\n\r\n")
        self.assertEqual(str(ctx.exception), "malformed header line: b': v'")

    def test_control_char_in_value_rejected(self):
        # 历史校验：值里控制字符非法（tab 除外）
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"GET / HTTP/1.1\r\nX-A: bad\x01value\r\n\r\n")
        self.assertEqual(
            str(ctx.exception), "malformed header line: b'X-A: bad\\x01value'"
        )

    def test_fold_continuation(self):
        r = parse_request(b"GET / HTTP/1.1\r\nX-A: 1\n\t2\n  3\r\n\r\n")
        self.assertEqual(r.header("x-a"), "1 2 3")

    def test_name_with_space_tolerated(self):
        # 历史容错：头名字里的空格不校验，照收
        r = parse_request(b"GET / HTTP/1.1\r\nX Weird: v\r\n\r\n")
        self.assertEqual(r.header("x-weird"), None)
        self.assertEqual(r.headers[0], ("X Weird", "v"))

    def test_fold_without_prev_raises(self):
        with self.assertRaises(ParseError):
            parse_request(b"GET / HTTP/1.1\r\n orphan\r\n\r\n")

    def test_header_lookup(self):
        r = parse_request(b"GET / HTTP/1.1\r\nX-A: 1\r\nx-a: 2\r\n\r\n")
        self.assertEqual(r.header("X-A"), "1")
        self.assertEqual(r.header("x-a"), "1")
        self.assertIsNone(r.header("nope"))
        self.assertEqual(r.header("nope", "d"), "d")


class TestContentLength(unittest.TestCase):
    def test_body_bytes(self):
        r = parse_request(b"POST / HTTP/1.1\r\nContent-Length: 5\r\n\r\nhello")
        self.assertEqual(r.body, b"hello")
        r = parse_request(b"POST / HTTP/1.1\r\nContent-Length: 0\r\n\r\n")
        self.assertEqual(r.body, b"")

    def test_extra_after_body_ignored(self):
        r = parse_request(b"POST / HTTP/1.1\r\nContent-Length: 2\r\n\r\nhello")
        self.assertEqual(r.body, b"he")

    def test_truncated_body(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"POST / HTTP/1.1\r\nContent-Length: 10\r\n\r\nabc")
        self.assertEqual(str(ctx.exception), "truncated body: want 10, got 3")

    def test_cl_invalid(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"POST / HTTP/1.1\r\nContent-Length: abc\r\n\r\n")
        self.assertEqual(str(ctx.exception), "invalid content-length: 'abc'")
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"POST / HTTP/1.1\r\nContent-Length: -3\r\n\r\n")
        self.assertEqual(str(ctx.exception), "invalid content-length: '-3'")

    def test_cl_first_wins(self):
        r = parse_request(
            b"POST / HTTP/1.1\r\nContent-Length: 2\r\nContent-Length: 5\r\n\r\nhello"
        )
        self.assertEqual(r.body, b"he")

    def test_no_cl_no_te_extra_ignored(self):
        # 历史容错：没有 CL/TE 时 body 为空，头部后的剩余字节忽略
        r = parse_request(b"GET / HTTP/1.1\r\n\r\njunkjunk")
        self.assertEqual(r.body, b"")


class TestChunked(unittest.TestCase):
    def _head(self):
        return b"PUT / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"

    def test_simple(self):
        r = parse_request(self._head() + b"5\r\nhello\r\n0\r\n\r\n")
        self.assertEqual(r.body, b"hello")
        # 最后一块后面直接 EOF 也能收尾（历史容错）
        r = parse_request(self._head() + b"0\r\n")
        self.assertEqual(r.body, b"")

    def test_multi_chunk_concat(self):
        r = parse_request(self._head() + b"3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n")
        self.assertEqual(r.body, b"abcde")

    def test_uppercase_hex_and_extension(self):
        r = parse_request(self._head() + b"A;flow=9\r\n" + b"a" * 10 + b"\r\n0\r\n\r\n")
        self.assertEqual(r.body, b"a" * 10)

    def test_trailers_consumed_not_headers(self):
        r = parse_request(
            self._head() + b"0\r\nX-Trailer: t\r\nX-Trailer2: u\r\n\r\n"
        )
        self.assertEqual(r.body, b"")
        self.assertEqual(r.headers, [("Transfer-Encoding", "chunked")])

    def test_chunked_beats_content_length(self):
        # 历史行为：TE 在时 CL 忽略
        r = parse_request(
            b"PUT / HTTP/1.1\r\nContent-Length: 3\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"5\r\nhello\r\n0\r\n\r\n"
        )
        self.assertEqual(r.body, b"hello")

    def test_bad_chunk_size(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(self._head() + b"zz\r\n")
        self.assertEqual(str(ctx.exception), "bad chunk size: b'zz'")
        with self.assertRaises(ParseError) as ctx:
            parse_request(self._head() + b"-1\r\n")
        self.assertEqual(str(ctx.exception), "bad chunk size: b'-1'")

    def test_truncated_chunk(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(self._head() + b"5\r\nhe")
        self.assertEqual(str(ctx.exception), "truncated chunk: want 5, got 2")

    def test_bad_chunk_terminator(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(self._head() + b"5\r\nhelloXX\r\n0\r\n\r\n")
        self.assertEqual(str(ctx.exception), "bad chunk terminator: b'XX'")

    def test_unsupported_te(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(b"PUT / HTTP/1.1\r\nTransfer-Encoding: gzip\r\n\r\n")
        self.assertEqual(str(ctx.exception), "unsupported transfer-encoding: gzip")

    def test_chunk_size_line_too_long(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(self._head() + b"f" * 9000 + b"\r\n0\r\n\r\n")
        self.assertEqual(str(ctx.exception), "line too long: 9001 bytes")

    def test_eof_before_chunk_size(self):
        with self.assertRaises(ParseError) as ctx:
            parse_request(self._head() + b"5\r\nhello\r\n")
        self.assertEqual(str(ctx.exception), "truncated chunk")


class TestHttpRequest(unittest.TestCase):
    def test_fresh_instance_and_bytes_body(self):
        r = HttpRequest()
        self.assertIsNone(r.method)
        self.assertIsNone(r.target)
        self.assertIsNone(r.version)
        self.assertEqual(r.headers, [])
        self.assertEqual(r.body, b"")
        # body 原样字节，不做解码
        r = parse_request(
            b"POST / HTTP/1.1\r\nContent-Length: 3\r\n\r\n\xff\xfe\x00"
        )
        self.assertEqual(r.body, b"\xff\xfe\x00")


if __name__ == "__main__":
    unittest.main()
