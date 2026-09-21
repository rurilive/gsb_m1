"""单线程对拍：同一段随机操作打给 LRUCache 和参考实现，逐项比对。"""

import unittest

import support  # noqa: F401  先挂 sys.path

from lruvault import LRUCache
from lruvault.reference import PlainLRU, apply_ops, random_ops


def build(seed, count, key_space, capacity):
    """把同一段操作分别打给两个实现，收集全部的观测量。"""
    ops = random_ops(seed, count, key_space)
    sentinel = object()
    seen = {}
    for name, cls in (("cache", LRUCache), ("ref", PlainLRU)):
        evicted = []
        target = cls(capacity=capacity,
                     on_evict=lambda k, v: evicted.append((k, v)))
        results = apply_ops(target, ops, default=sentinel)
        seen[name] = {
            "results": results,
            "keys": target.keys(),
            "snapshot": target.snapshot(),
            "stats": target.stats(),
            "evicted": evicted,
            "sentinel": sentinel,
        }
    return seen


class ParityTest(unittest.TestCase):

    def check_seed(self, seed, count=400, key_space=12, capacity=5):
        seen = build(seed, count, key_space, capacity)
        cache, ref = seen["cache"], seen["ref"]
        for index, (got, want) in enumerate(zip(cache["results"], ref["results"])):
            if want is ref["sentinel"]:
                self.assertIs(got, cache["sentinel"],
                              "第 %d 次 get 该落空却没有, seed=%d" % (index, seed))
            else:
                self.assertEqual(got, want,
                                 "第 %d 次 get 结果不一致, seed=%d" % (index, seed))
        self.assertEqual(cache["keys"], ref["keys"], "新旧次序不一致 seed=%d" % seed)
        self.assertEqual(cache["snapshot"], ref["snapshot"])
        self.assertEqual(cache["evicted"], ref["evicted"])
        self.assertEqual(tuple(cache["stats"]), tuple(ref["stats"]))
        self.assertLessEqual(cache["stats"].live, capacity)

    def test_random_ops_match_reference(self):
        for seed in range(5):
            with self.subTest(seed=seed):
                self.check_seed(seed)

    def test_tiny_capacity_replay(self):
        for seed in range(20, 25):
            with self.subTest(seed=seed):
                self.check_seed(seed, count=200, key_space=6, capacity=2)

    def test_generous_capacity_keeps_everything(self):
        for seed in range(40, 43):
            with self.subTest(seed=seed):
                self.check_seed(seed, count=200, key_space=8, capacity=64)


if __name__ == "__main__":
    unittest.main()
