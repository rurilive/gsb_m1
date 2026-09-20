"""按块喂入的流式解码基线。"""

import unittest

from wirepack.errors import DecodeError
from wirepack.records import RECORD_SIZE, Record, pack_record
from wirepack.stream import RecordStream, chunked, iter_records


def sample():
    return [
        Record(11, "data", "n1"),
        Record(12, "data", "n2", flags=3),
        Record(13, "ack", ""),
        Record(14, "ctrl", "node-7"),
    ]


def blob(records=None):
    return b"".join(pack_record(r) for r in (records or sample()))


class ChunkedTest(unittest.TestCase):
    def test_splits_into_fixed_pieces(self):
        self.assertEqual(chunked(b"abcdef", 4), [b"abcd", b"ef"])

    def test_exact_multiple_has_no_empty_tail(self):
        self.assertEqual(chunked(b"abcd", 2), [b"ab", b"cd"])

    def test_empty_input(self):
        self.assertEqual(chunked(b"", 4), [])

    def test_bad_size(self):
        with self.assertRaises(ValueError):
            chunked(b"abc", 0)


class FeedTest(unittest.TestCase):
    def test_whole_blob_in_one_chunk(self):
        stream = RecordStream()
        records = stream.feed(blob())
        self.assertEqual(records, sample())
        self.assertEqual(stream.offset, 4 * RECORD_SIZE)
        self.assertEqual(stream.pending, 0)
        self.assertEqual(stream.finish(), [])

    def test_one_byte_at_a_time(self):
        stream = RecordStream()
        seen = []
        for piece in chunked(blob(), 1):
            seen.extend(stream.feed(piece))
        self.assertEqual(seen, sample())
        self.assertEqual(stream.finish(), [])

    def test_split_in_the_middle_of_a_record(self):
        stream = RecordStream()
        self.assertEqual(stream.feed(blob()[:7]), [])
        self.assertEqual(stream.pending, 7)
        records = stream.feed(blob()[7:])
        self.assertEqual(records, sample())

    def test_one_chunk_can_hold_several_records(self):
        stream = RecordStream()
        first = stream.feed(blob(sample()[:2]))
        self.assertEqual(first, sample()[:2])
        self.assertEqual(stream.records, 2)

    def test_empty_chunk_is_harmless(self):
        stream = RecordStream()
        self.assertEqual(stream.feed(b""), [])
        self.assertEqual(stream.offset, 0)

    def test_memoryview_and_bytearray_accepted(self):
        stream = RecordStream()
        self.assertEqual(stream.feed(memoryview(blob(sample()[:1]))), sample()[:1])
        self.assertEqual(stream.feed(bytearray(blob(sample()[1:]))), sample()[1:])

    def test_str_chunk_rejected(self):
        with self.assertRaises(TypeError):
            RecordStream().feed("abcd")


class TruncatedTailTest(unittest.TestCase):
    def test_finish_on_clean_stream(self):
        stream = RecordStream()
        stream.feed(blob(sample()[:1]))
        self.assertEqual(stream.finish(), [])

    def test_finish_reports_leftover(self):
        stream = RecordStream()
        stream.feed(blob(sample()[:2]) + b"\x00\x01\x02")
        with self.assertRaises(DecodeError) as caught:
            stream.finish()
        self.assertEqual(caught.exception.field, "record")
        self.assertEqual(caught.exception.offset, 2 * RECORD_SIZE)

    def test_offset_is_absolute(self):
        stream = RecordStream()
        stream.feed(blob(sample()[:3]))
        stream.feed(b"\x00" * 9)
        with self.assertRaises(DecodeError) as caught:
            stream.finish()
        self.assertEqual(caught.exception.offset, 3 * RECORD_SIZE)

    def test_iter_records_stops_at_truncated_tail(self):
        pieces = chunked(blob(sample()) + b"\xaa\xbb", 5)
        with self.assertRaises(DecodeError):
            list(iter_records(pieces))

    def test_stream_can_continue_after_short_chunks(self):
        stream = RecordStream()
        stream.feed(blob(sample()[:2]))
        rest = blob(sample()[2:])
        self.assertEqual(stream.feed(rest[:3]), [])
        self.assertEqual(stream.feed(rest[3:]), sample()[2:])
        self.assertEqual(stream.offset, 4 * RECORD_SIZE)


class BadRecordTest(unittest.TestCase):
    def test_bad_record_mid_stream_raises(self):
        good = pack_record(sample()[0])
        bad = b"\x00\x00\x00\x01\x09" + b"\x00" * 11
        stream = RecordStream()
        with self.assertRaises(DecodeError) as caught:
            stream.feed(good + bad)
        self.assertEqual(caught.exception.field, "kind")
        self.assertEqual(caught.exception.offset, RECORD_SIZE + 4)

    def test_stream_keeps_leftover_after_error(self):
        stream = RecordStream()
        with self.assertRaises(DecodeError):
            stream.feed(b"\x00\x00\x00\x01\x09" + b"\x00" * 11)
        self.assertEqual(stream.offset, 0)
        self.assertEqual(stream.pending, RECORD_SIZE)


class IterRecordsTest(unittest.TestCase):
    def test_iterator_matches_stream(self):
        self.assertEqual(list(iter_records(chunked(blob(), 7))), sample())

    def test_empty_input(self):
        self.assertEqual(list(iter_records([])), [])

    def test_single_record(self):
        self.assertEqual(list(iter_records([blob(sample()[:1])])), sample()[:1])


if __name__ == "__main__":
    unittest.main()
