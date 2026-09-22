"""事件解析与日志行构造的既有行为锁定。"""

import unittest

from cdcparse.events import (
    ParseError,
    begin_line,
    commit_line,
    data_line,
    ddl_line,
    parse_line,
    txn_lines,
)


class ParseLineTest(unittest.TestCase):
    def test_begin_fields(self):
        event = parse_line('{"pos": 3, "type": "begin", "xid": 9}')
        self.assertEqual(event.kind, "begin")
        self.assertEqual(event.pos, 3)
        self.assertEqual(event.xid, 9)

    def test_commit_fields(self):
        event = parse_line(commit_line(8, 9))
        self.assertEqual(event.kind, "commit")
        self.assertEqual(event.pos, 8)
        self.assertEqual(event.xid, 9)

    def test_data_fields(self):
        event = parse_line(data_line(4, 9, "update", "orders", {"id": 1, "amount": 20}))
        self.assertEqual(event.kind, "data")
        self.assertEqual(event.op, "update")
        self.assertEqual(event.table, "orders")
        self.assertEqual(event.row, {"id": 1, "amount": 20})

    def test_ddl_fields(self):
        event = parse_line(ddl_line(5, "alter table orders add column note varchar(32)"))
        self.assertEqual(event.kind, "ddl")
        self.assertEqual(event.sql, "alter table orders add column note varchar(32)")
        self.assertIsNone(event.xid)

    def test_as_change_data(self):
        event = parse_line(data_line(2, 1, "insert", "items", {"id": 7}))
        self.assertEqual(
            event.as_change(),
            {"pos": 2, "xid": 1, "op": "insert", "table": "items", "row": {"id": 7}},
        )

    def test_as_change_ddl(self):
        event = parse_line(ddl_line(6, "drop table items"))
        self.assertEqual(
            event.as_change(),
            {"pos": 6, "xid": None, "op": "ddl", "table": None, "sql": "drop table items"},
        )

    def test_as_change_rejects_boundary_events(self):
        with self.assertRaises(ValueError):
            parse_line(begin_line(1, 2)).as_change()
        with self.assertRaises(ValueError):
            parse_line(commit_line(3, 2)).as_change()

    def test_row_is_copied_in_change(self):
        event = parse_line(data_line(2, 1, "insert", "items", {"id": 7}))
        change = event.as_change()
        change["row"]["id"] = 99
        self.assertEqual(event.row, {"id": 7})

    def test_bad_json_raises(self):
        with self.assertRaises(ParseError):
            parse_line('{"pos": 1, "type": "begin"')

    def test_non_object_raises(self):
        with self.assertRaises(ParseError):
            parse_line("[1, 2, 3]")

    def test_unknown_type_raises(self):
        with self.assertRaises(ParseError):
            parse_line('{"pos": 1, "type": "heartbeat"}')

    def test_bad_pos_raises(self):
        for text in ('{"pos": "1", "type": "begin", "xid": 2}',
                     '{"type": "begin", "xid": 2}',
                     '{"pos": 0, "type": "begin", "xid": 2}',
                     '{"pos": true, "type": "begin", "xid": 2}'):
            with self.assertRaises(ParseError, msg=text):
                parse_line(text)

    def test_missing_xid_raises(self):
        with self.assertRaises(ParseError):
            parse_line('{"pos": 1, "type": "commit"}')

    def test_bad_op_raises(self):
        with self.assertRaises(ParseError):
            parse_line('{"pos": 2, "type": "data", "xid": 1, "op": "merge",'
                       ' "table": "t", "row": {}}')

    def test_missing_row_raises(self):
        with self.assertRaises(ParseError):
            parse_line('{"pos": 2, "type": "data", "xid": 1, "op": "insert",'
                       ' "table": "t"}')

    def test_ddl_without_sql_raises(self):
        with self.assertRaises(ParseError):
            parse_line('{"pos": 2, "type": "ddl"}')


class TxnLinesTest(unittest.TestCase):
    def test_positions_are_consecutive(self):
        lines, next_pos = txn_lines(10, 5, [("insert", "t", {"id": 1}),
                                            ("delete", "t", {"id": 2})])
        self.assertEqual(len(lines), 4)
        self.assertEqual([parse_line(line).pos for line in lines], [10, 11, 12, 13])
        self.assertEqual(parse_line(lines[0]).kind, "begin")
        self.assertEqual(parse_line(lines[-1]).kind, "commit")
        self.assertEqual(next_pos, 14)

    def test_empty_txn_is_begin_commit_pair(self):
        lines, next_pos = txn_lines(4, 6, [])
        self.assertEqual(len(lines), 2)
        self.assertEqual(next_pos, 6)


if __name__ == "__main__":
    unittest.main()
