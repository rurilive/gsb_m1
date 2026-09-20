"""MultipartParser、PartCollector 和 reference 现有行为的锁定测试。"""

import unittest

from chunkmime import (
    DiscardSink,
    MultipartParser,
    ParseError,
    Part,
    PartCollector,
    parse_all,
)

BOUNDARY = b"abc123"


def text_part(name):
    return (
        b'Content-Disposition: form-data; name="' + name + b'"\r\n'
        b"Content-Type: text/plain"
    )


def file_part(name, filename):
    return (
        b'Content-Disposition: form-data; name="' + name + b'"; filename="'
        + filename + b'"\r\nContent-Type: application/octet-stream'
    )


def build(parts, preamble=b"", epilogue=b""):
    """拼一份完整的 multipart body,parts 是 (头部块, 正文) 的列表。"""
    out = bytearray(preamble)
    for head, data in parts:
        if out and not out.endswith(b"\r\n"):
            out += b"\r\n"
        out += b"--" + BOUNDARY + b"\r\n" + head + b"\r\n\r\n" + data
    out += b"\r\n--" + BOUNDARY + b"--\r\n" + epilogue
    return bytes(out)


def run_parser(body, cuts=None, boundary=BOUNDARY):
    """把 body 按 cuts 给出的偏移切块喂进去,返回解析出的 parts。"""
    collector = PartCollector()
    parser = MultipartParser(boundary, collector)
    if cuts:
        pos = 0
        for cut in cuts:
            parser.feed(body[pos:cut])
            pos = cut
        parser.feed(body[pos:])
    else:
        parser.feed(body)
    parser.finish()
    return collector.parts()


FORM = [
    (text_part(b"title"), b"quarterly report draft"),
    (text_part(b"tags"), b"alpha beta gamma"),
    (file_part(b"upload", b"note.txt"), b"first line\nsecond line\n"),
]


class TestMultipartParser(unittest.TestCase):
    def test_single_field(self):
        body = build([(text_part(b"title"), b"hello")])
        parts = run_parser(body)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].name, "title")
        self.assertEqual(parts[0].data, b"hello")

    def test_fields_come_out_in_order(self):
        parts = run_parser(build(FORM))
        self.assertEqual([p.name for p in parts], ["title", "tags", "upload"])
        self.assertEqual(
            [p.data for p in parts],
            [b"quarterly report draft", b"alpha beta gamma",
             b"first line\nsecond line\n"],
        )

    def test_file_part_params_and_binary_body(self):
        payload = bytes(range(256))
        body = build([(file_part(b"upload", b"blob.bin"), payload)])
        parts = run_parser(body)
        self.assertEqual(parts[0].filename, "blob.bin")
        self.assertEqual(parts[0].data, payload)

    def test_headers_and_params_are_exposed(self):
        parts = run_parser(build(FORM))
        head = parts[2].headers
        self.assertEqual(head["content-type"], "application/octet-stream")
        self.assertEqual(parts[2].params["name"], "upload")
        self.assertEqual(parts[2].filename, "note.txt")

    def test_quoted_filename_with_space(self):
        body = build([(file_part(b"upload", b"my report.txt"), b"x")])
        parts = run_parser(body)
        self.assertEqual(parts[0].filename, "my report.txt")

    def test_unquoted_param_value(self):
        head = b'Content-Disposition: form-data; name=plain; filename=r.txt'
        body = build([(head, b"x")])
        parts = run_parser(body)
        self.assertEqual(parts[0].name, "plain")
        self.assertEqual(parts[0].filename, "r.txt")

    def test_empty_file_part(self):
        body = build([(file_part(b"upload", b"empty.txt"), b"")])
        parts = run_parser(body)
        self.assertEqual(parts[0].filename, "empty.txt")
        self.assertEqual(parts[0].data, b"")

    def test_preamble_and_epilogue_are_ignored(self):
        body = build(FORM, preamble=b"ignore me", epilogue=b"ignore me too")
        parts = run_parser(body)
        self.assertEqual([p.name for p in parts], ["title", "tags", "upload"])

    def test_content_with_boundary_lookalike_is_kept(self):
        # 正文里有长得像分隔行的字节:前缀不完整,或者不在行首
        payload = b"snippet: \r\n--abc12X and mid-line --abc123 text"
        body = build([(file_part(b"upload", b"notes.txt"), payload)])
        parts = run_parser(body)
        self.assertEqual(parts[0].data, payload)

    def test_trailing_crlf_not_part_of_content(self):
        body = build([(text_part(b"title"), b"hello")])
        parts = run_parser(body)
        self.assertFalse(parts[0].data.endswith(b"\r\n"))

    def test_chunked_feeding_agrees_with_whole(self):
        whole = build(FORM)
        cuts = [
            whole.index(b"report") + 3,
            whole.index(b"gamma") + 2,
            whole.index(b"second") + 2,
        ]
        chunked = run_parser(whole, cuts=cuts)
        self.assertEqual(chunked, run_parser(whole))

    def test_str_boundary_is_accepted(self):
        body = build([(text_part(b"title"), b"hello")])
        parts = run_parser(body, boundary="abc123")
        self.assertEqual(parts[0].name, "title")

    def test_discard_sink_counts(self):
        sink = DiscardSink()
        parser = MultipartParser(BOUNDARY, sink)
        parser.feed(build(FORM))
        parser.finish()
        self.assertEqual(sink.parts, 3)
        self.assertEqual(sink.names, ["title", "tags", "upload"])
        self.assertEqual(sink.bytes_in, len(b"quarterly report draft")
                         + len(b"alpha beta gamma")
                         + len(b"first line\nsecond line\n"))


class TestReference(unittest.TestCase):
    def test_reference_agrees_on_simple_body(self):
        body = build(FORM)
        parts = parse_all(body, BOUNDARY)
        self.assertEqual(parts, run_parser(body))

    def test_reference_agrees_on_body_with_preamble(self):
        body = build(FORM, preamble=b"junk\r\n", epilogue=b"\r\ntail")
        parts = parse_all(body, BOUNDARY)
        self.assertEqual(parts, run_parser(body))

    def test_reference_rejects_body_without_boundary(self):
        with self.assertRaises(ParseError):
            parse_all(b"no boundary here", BOUNDARY)

    def test_reference_rejects_unterminated_part(self):
        body = build([(text_part(b"title"), b"hello")])
        with self.assertRaises(ParseError):
            parse_all(body[:-9], BOUNDARY)

    def test_reference_agrees_on_unquoted_params(self):
        head = b"Content-Disposition: form-data; name=plain; filename=r.txt"
        body = build([(head, b"x")])
        self.assertEqual(parse_all(body, BOUNDARY), run_parser(body))

    def test_reference_keeps_boundary_lookalike_in_content(self):
        payload = b"line\r\n--abc12X more"
        body = build([(file_part(b"upload", b"notes.txt"), payload)])
        parts = parse_all(body, BOUNDARY)
        self.assertEqual(parts[0].data, payload)


class TestPart(unittest.TestCase):
    def test_part_equality(self):
        self.assertEqual(Part({"a": "b"}, {"name": "x"}, b"d"),
                         Part({"a": "b"}, {"name": "x"}, b"d"))
        self.assertNotEqual(Part({}, {}, b"d"), Part({}, {}, b"e"))

    def test_part_repr(self):
        text = repr(Part({}, {"name": "x", "filename": "y.txt"}, b"0123"))
        self.assertIn("x", text)
        self.assertIn("y.txt", text)
        self.assertIn("4", text)


if __name__ == "__main__":
    unittest.main()
