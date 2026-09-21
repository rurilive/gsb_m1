"""统计快照基线。

锁住 collect 的口径：行数、各列基数、采集时的版本号，以及过期判断。
"""

import unittest

from jqplan.stats import Stats
from jqplan.table import Table


def make_tables():
    users = Table("users", ["uid", "city"])
    users.insert_many([(1, "bj"), (2, "sh"), (3, "bj"), (4, "bj")])
    orders = Table("orders", ["oid", "uid"])
    orders.insert_many([(10, 1), (11, 1), (12, 4)])
    return users, orders


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.users, self.orders = make_tables()
        self.stats = Stats.collect([self.users, self.orders])

    def test_row_counts(self):
        self.assertEqual(self.stats.row_count("users"), 4)
        self.assertEqual(self.stats.row_count("orders"), 3)
        self.assertEqual(self.stats.table_names(), ("orders", "users"))

    def test_distinct_counts(self):
        self.assertEqual(self.stats.distinct("users", "city"), 2)
        self.assertEqual(self.stats.distinct("users", "uid"), 4)
        self.assertEqual(self.stats.distinct("orders", "uid"), 2)

    def test_revision_recorded(self):
        self.assertEqual(self.stats.revision("users"), self.users.revision)

    def test_missing_table_and_column_are_none(self):
        partial = Stats.collect([self.users])
        self.assertIsNone(partial.row_count("orders"))
        self.assertIsNone(partial.distinct("orders", "uid"))
        self.assertEqual(partial.stale([self.users, self.orders]), ("orders",))
        self.assertIsNone(self.stats.distinct("users", "nope"))

    def test_empty_table_is_counted_as_zero(self):
        empty = Table("empty", ["a"])
        stats = Stats.collect([empty])
        self.assertEqual(stats.row_count("empty"), 0)
        self.assertEqual(stats.distinct("empty", "a"), 0)

    def test_stale_tracks_table_writes(self):
        self.assertEqual(self.stats.stale([self.users, self.orders]), ())
        self.users.insert((5, "gz"))
        self.assertEqual(self.stats.stale([self.users, self.orders]), ("users",))
        fresh = Stats.collect([self.users, self.orders])
        self.assertEqual(fresh.stale([self.users, self.orders]), ())

    def test_snapshot_is_independent_of_later_writes(self):
        self.orders.insert((13, 2))
        self.assertEqual(self.stats.row_count("orders"), 3)
        self.assertEqual(self.stats.revision("orders"), 3)


if __name__ == "__main__":
    unittest.main()
