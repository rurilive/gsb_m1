"""基线测试：锁住全局锁事务引擎现在的行为，一字不改。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from txbox import LockedTxn, TxnError


class LockedTxnBaselineTest(unittest.TestCase):
    def test_initial_data_visible(self):
        engine = LockedTxn({"a": 1})
        self.assertEqual(engine.committed, {"a": 1})

    def test_read_write_commit(self):
        engine = LockedTxn()
        engine.begin()
        engine.set("a", 1)
        self.assertEqual(engine.get("a"), 1)
        engine.commit()
        self.assertEqual(engine.committed, {"a": 1})

    def test_delete(self):
        engine = LockedTxn({"a": 1, "b": 2})
        engine.begin()
        engine.delete("a")
        engine.commit()
        self.assertEqual(engine.committed, {"b": 2})

    def test_rollback_restores_state(self):
        engine = LockedTxn({"a": 1})
        engine.begin()
        engine.set("a", 99)
        engine.set("b", 2)
        engine.rollback()
        self.assertEqual(engine.committed, {"a": 1})

    def test_operations_require_active_txn(self):
        engine = LockedTxn()
        with self.assertRaises(TxnError):
            engine.get("a")
        with self.assertRaises(TxnError):
            engine.set("a", 1)
        with self.assertRaises(TxnError):
            engine.commit()

    def test_no_concurrent_txn(self):
        engine = LockedTxn()
        engine.begin()
        with self.assertRaises(TxnError):
            engine.begin()
        engine.rollback()

    def test_commit_then_no_active(self):
        engine = LockedTxn()
        engine.begin()
        engine.commit()
        self.assertFalse(engine.active)
        with self.assertRaises(TxnError):
            engine.commit()

    def test_commit_is_atomic_against_untouched_keys(self):
        engine = LockedTxn({"keep": 7})
        engine.begin()
        engine.set("new", 8)
        engine.commit()
        self.assertEqual(engine.committed, {"keep": 7, "new": 8})


if __name__ == "__main__":
    unittest.main()
