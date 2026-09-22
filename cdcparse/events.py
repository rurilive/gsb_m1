"""事件模型、JSON 行解析与日志行构造。

一行一个事件：

    {"pos": 1, "type": "begin", "xid": 21}
    {"pos": 2, "type": "data", "xid": 21, "op": "insert",
     "table": "orders", "row": {"id": 1, "amount": 50}}
    {"pos": 3, "type": "commit", "xid": 21}
    {"pos": 4, "type": "ddl", "sql": "alter table orders add column note varchar(32)"}

pos 是上游日志里的位点，同一份日志里唯一且递增，但到达顺序不保证。
每条 data 事件都属于某个事务：由 begin 打开、commit 关闭，携带同一个 xid。
"""

import json

KINDS = ("begin", "commit", "data", "ddl")
OPS = ("insert", "update", "delete")


class ParseError(ValueError):
    """事件行不是合法 JSON，或缺少必需字段。"""


class Event:
    """一个解析后的事件。字段按类型取用。"""

    __slots__ = ("pos", "kind", "xid", "op", "table", "row", "sql", "raw")

    def __init__(self, pos, kind, raw=None, xid=None, op=None, table=None,
                 row=None, sql=None):
        self.pos = pos
        self.kind = kind
        self.raw = raw
        self.xid = xid
        self.op = op
        self.table = table
        self.row = row
        self.sql = sql

    def as_change(self):
        """转成给下游的变更字典；begin / commit 没有变更形态。"""
        if self.kind == "data":
            return {
                "pos": self.pos,
                "xid": self.xid,
                "op": self.op,
                "table": self.table,
                "row": dict(self.row),
            }
        if self.kind == "ddl":
            return {"pos": self.pos, "xid": None, "op": "ddl", "table": None,
                    "sql": self.sql}
        raise ValueError("事件类型 %r 转不出变更" % (self.kind,))

    def __repr__(self):
        return "Event(pos=%r, kind=%r, op=%r, table=%r)" % (
            self.pos, self.kind, self.op, self.table)

    def __eq__(self, other):
        if not isinstance(other, Event):
            return NotImplemented
        return (self.pos, self.kind, self.xid, self.op, self.table, self.row,
                self.sql) == (other.pos, other.kind, other.xid, other.op,
                              other.table, other.row, other.sql)

    def __hash__(self):
        return hash((self.pos, self.kind))


def _int_field(payload, name):
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParseError("字段 %s 需要整数，收到 %r" % (name, value))
    return value


def parse_line(text):
    """把一行文本解析成 Event，失败抛 ParseError。"""
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ParseError("不是合法 JSON: %s" % (exc,))
    if not isinstance(payload, dict):
        raise ParseError("事件行必须是 JSON 对象")
    kind = payload.get("type")
    if kind not in KINDS:
        raise ParseError("未知事件类型 %r" % (kind,))
    pos = _int_field(payload, "pos")
    if pos <= 0:
        raise ParseError("pos 必须为正整数，收到 %r" % (pos,))
    if kind == "ddl":
        sql = payload.get("sql")
        if not isinstance(sql, str) or not sql:
            raise ParseError("ddl 事件缺少非空 sql")
        return Event(pos, kind, raw=text, sql=sql)
    xid = _int_field(payload, "xid")
    if kind in ("begin", "commit"):
        return Event(pos, kind, raw=text, xid=xid)
    op = payload.get("op")
    if op not in OPS:
        raise ParseError("未知操作类型 %r" % (op,))
    table = payload.get("table")
    if not isinstance(table, str) or not table:
        raise ParseError("data 事件缺少非空表名")
    row = payload.get("row")
    if not isinstance(row, dict):
        raise ParseError("data 事件缺少 row 对象")
    return Event(pos, kind, raw=text, xid=xid, op=op, table=table, row=row)


def _dump(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def begin_line(pos, xid):
    return _dump({"pos": pos, "type": "begin", "xid": xid})


def data_line(pos, xid, op, table, row):
    return _dump({"pos": pos, "type": "data", "xid": xid, "op": op,
                  "table": table, "row": row})


def commit_line(pos, xid):
    return _dump({"pos": pos, "type": "commit", "xid": xid})


def ddl_line(pos, sql):
    return _dump({"pos": pos, "type": "ddl", "sql": sql})


def txn_lines(start_pos, xid, changes):
    """把一组行变更包成 begin/data.../commit 行，位点从 start_pos 起连号。

    changes 是 (op, table, row) 的可迭代。
    返回 (lines, next_pos)，next_pos 是下一段可用的位点。
    """
    lines = [begin_line(start_pos, xid)]
    pos = start_pos
    for op, table, row in changes:
        pos += 1
        lines.append(data_line(pos, xid, op, table, row))
    pos += 1
    lines.append(commit_line(pos, xid))
    return lines, pos + 1
