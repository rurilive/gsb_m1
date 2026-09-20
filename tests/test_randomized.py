"""随机对拍:同一份 body 按随机位置切块喂 MultipartParser,结果要和
reference.parse_all 全量解析逐字段一致;半路断掉的流两边都要报错。"""

import random
import unittest

from chunkmime import MultipartParser, ParseError, PartCollector, parse_all

BOUNDARY = b"abc123"
MARKER = b"\r\n--" + BOUNDARY
CLOSING = MARKER + b"--"


def random_token(rng, alphabet, lo, hi):
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(lo, hi)))


def random_filename(rng):
    name = random_token(rng, "abcXYZ019 ._-", 1, 12)
    pos = rng.randint(0, len(name))
    # 掺入要转义的字符:引号、反斜杠
    name = name[:pos] + rng.choice(['"', "\\"]) + name[pos:]
    return name


def quote(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def random_payload(rng):
    chunks = []
    for _ in range(rng.randint(0, 6)):
        r = rng.random()
        if r < 0.4:
            chunks.append(rng.randbytes(rng.randint(0, 64)))
        elif r < 0.65:
            # 分隔行的半截前缀,后面接的字节让它对不上
            k = rng.randint(2, len(MARKER) - 1)
            chunks.append(MARKER[:k] + b"?")
        elif r < 0.85:
            # 完整分隔行本体,但尾巴不是 CRLF 或 --,不算分隔行
            chunks.append(MARKER + rng.choice([b"XX", b"-X", b"\rX", b"\n\n"]))
        else:
            # 不在行首的分隔行字样
            chunks.append(b"mid-line --" + BOUNDARY + b" text")
    return b"".join(chunks)


def random_body(rng):
    parts = []
    for _ in range(rng.randint(1, 4)):
        name = random_token(rng, "abcdefg123_-", 1, 8)
        if rng.random() < 0.5:
            head = 'Content-Disposition: form-data; name="%s"' % name
        else:
            filename = random_filename(rng)
            head = ('Content-Disposition: form-data; name="%s"; filename="%s"'
                    % (name, quote(filename)))
            head += "\r\nContent-Type: application/octet-stream"
        parts.append((head.encode("latin-1"), random_payload(rng)))
    out = bytearray()
    if rng.random() < 0.3:
        out += rng.randbytes(rng.randint(1, 16)).replace(MARKER, b"")
        out += b"\r\n"
    for head, data in parts:
        out += b"--" + BOUNDARY + b"\r\n" + head + b"\r\n\r\n" + data
    out += CLOSING
    if rng.random() < 0.3:
        out += b"\r\nepilogue ignored"
    return bytes(out)


def feed_in_chunks(rng, body):
    collector = PartCollector()
    parser = MultipartParser(BOUNDARY, collector)
    pos = 0
    while pos < len(body):
        step = rng.choice([1, 2, 3, rng.randint(1, 16),
                           rng.randint(1, 256), rng.randint(1, 8192)])
        parser.feed(body[pos:pos + step])
        pos += step
    parser.finish()
    return collector.parts()


class TestRandomChunking(unittest.TestCase):
    def test_random_bodies_match_reference(self):
        rng = random.Random(20260921)
        for _ in range(300):
            body = random_body(rng)
            try:
                expected = parse_all(body, BOUNDARY)
            except ParseError:
                # 随机内容凑出了真分隔行,结构坏了:解析器也得报错
                with self.assertRaises(ParseError):
                    feed_in_chunks(rng, body)
                continue
            self.assertEqual(feed_in_chunks(rng, body), expected)

    def test_byte_by_byte_feeding(self):
        rng = random.Random(7)
        for _ in range(20):
            body = random_body(rng)
            try:
                expected = parse_all(body, BOUNDARY)
            except ParseError:
                continue
            collector = PartCollector()
            parser = MultipartParser(BOUNDARY, collector)
            for off in range(len(body)):
                parser.feed(body[off:off + 1])
            parser.finish()
            self.assertEqual(collector.parts(), expected)

    def test_truncated_stream_raises(self):
        rng = random.Random(99)
        for _ in range(100):
            body = random_body(rng)
            closing = body.rindex(CLOSING)
            # 在收尾分隔行写完之前断掉,两边都必须报错
            cut = rng.randint(1, closing + len(CLOSING) - 1)
            piece = body[:cut]
            with self.assertRaises(ParseError):
                parse_all(piece, BOUNDARY)
            parser = MultipartParser(BOUNDARY, PartCollector())
            with self.assertRaises(ParseError):
                pos = 0
                while pos < len(piece):
                    step = rng.randint(1, 64)
                    parser.feed(piece[pos:pos + step])
                    pos += step
                parser.finish()


if __name__ == "__main__":
    unittest.main()
