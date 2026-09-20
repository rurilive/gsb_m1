"""大文件流式解析:50MB 正文边收边交出去,解析器自身内存有界。"""

import os
import time
import tracemalloc
import unittest

from chunkmime import DiscardSink, MultipartParser

BOUNDARY = b"abc123"
CHUNK = 256 * 1024


class TestLargeUpload(unittest.TestCase):
    def test_50mb_file_streams_within_budget(self):
        payload = os.urandom(50 * 1024 * 1024)
        body = (
            b'--abc123\r\nContent-Disposition: form-data; name="upload";'
            b' filename="big.bin"\r\nContent-Type: application/octet-stream'
            b"\r\n\r\n" + payload + b"\r\n--abc123--\r\n"
        )
        sink = DiscardSink()
        parser = MultipartParser(BOUNDARY, sink)
        tracemalloc.start()
        start = time.monotonic()
        for off in range(0, len(body), CHUNK):
            parser.feed(body[off:off + CHUNK])
        parser.finish()
        elapsed = time.monotonic() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(sink.parts, 1)
        self.assertEqual(sink.bytes_in, len(payload))
        self.assertLess(peak, 8 * 1024 * 1024,
                        "峰值内存 %.1fMB 超了 8MB" % (peak / 1048576))
        self.assertLess(elapsed, 10, "耗时 %.1fs 超了 10s" % elapsed)


if __name__ == "__main__":
    unittest.main()
