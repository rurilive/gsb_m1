"""统计快照。

Stats.collect 扫一遍表，记下每张表的行数、各列基数和采集当时的 revision。
读统计的一方只看这份快照，不再碰表本身。
"""


class Stats:
    """一批表的统计快照，按表名索引。"""

    def __init__(self, entries=None):
        """entries 形如 {表名: {"rows": int, "distinct": {列名: int}, "revision": int}}。"""
        self._entries = {}
        for name, entry in (entries or {}).items():
            self._entries[name] = {
                "rows": int(entry["rows"]),
                "distinct": dict(entry.get("distinct", {})),
                "revision": entry.get("revision"),
            }

    @classmethod
    def collect(cls, tables):
        """扫描给定的一批表，生成快照。"""
        entries = {}
        for table in tables:
            entries[table.name] = {
                "rows": table.row_count(),
                "distinct": {col: table.distinct(col) for col in table.columns},
                "revision": table.revision,
            }
        return cls(entries)

    def table_names(self):
        """快照覆盖的表名，排序后返回。"""
        return tuple(sorted(self._entries))

    def row_count(self, table_name):
        """表行数，没采集过这张表返回 None。"""
        entry = self._entries.get(table_name)
        return None if entry is None else entry["rows"]

    def distinct(self, table_name, column):
        """列基数，表或列不在快照里返回 None。"""
        entry = self._entries.get(table_name)
        if entry is None:
            return None
        return entry["distinct"].get(column)

    def revision(self, table_name):
        """采集时表的 revision，没采集过返回 None。"""
        entry = self._entries.get(table_name)
        return None if entry is None else entry["revision"]

    def stale(self, tables):
        """列出对不上的表名：没采集过，或者采集之后表又被写过。"""
        names = []
        for table in tables:
            entry = self._entries.get(table.name)
            if entry is None or entry["revision"] != table.revision:
                names.append(table.name)
        return tuple(sorted(names))

    def __repr__(self):
        return f"Stats(tables={self.table_names()!r})"
