"""朴素全量平均的锁定测试。

本文件把改造之前的 Meter 行为一字锁死：累加、平均、计数、求和不
淘汰样本，reset 回到刚建立时的状态，非法样本在入口处报错。新增的
滑动窗口速率、多窗口、分位、衰减、快照等能力另开测试文件，本文件
一字不改。
"""

import unittest

from movavg.meter import Meter


class TestMeterArithmetic(unittest.TestCase):
    def test_new_meter_has_zero_mean(self):
        self.assertEqual(Meter().mean(), 0.0)

    def test_new_meter_counts_zero_samples(self):
        self.assertEqual(Meter().count(), 0)

    def test_new_meter_totals_zero(self):
        self.assertEqual(Meter().total(), 0.0)

    def test_mean_of_single_sample(self):
        m = Meter()
        m.record(7)
        self.assertEqual(m.mean(), 7.0)

    def test_mean_of_int_samples(self):
        m = Meter()
        for v in (1, 2, 3, 4):
            m.record(v)
        self.assertEqual(m.mean(), 2.5)

    def test_mean_of_float_samples(self):
        m = Meter()
        for v in (0.5, 1.5):
            m.record(v)
        self.assertEqual(m.mean(), 1.0)

    def test_total_is_plain_sum(self):
        m = Meter()
        for v in (2, 3, 5):
            m.record(v)
        self.assertEqual(m.total(), 10.0)

    def test_count_tracks_every_sample(self):
        m = Meter()
        for i in range(1000):
            m.record(i)
        self.assertEqual(m.count(), 1000)

    def test_mean_is_exact_division_of_total(self):
        m = Meter()
        for v in (1, 2, 4):
            m.record(v)
        self.assertEqual(m.mean(), m.total() / m.count())

    def test_mean_accepts_negative_and_zero(self):
        m = Meter()
        for v in (-3, 0, 3):
            m.record(v)
        self.assertEqual(m.mean(), 0.0)


class TestMeterRetention(unittest.TestCase):
    def test_samples_are_never_evicted(self):
        m = Meter()
        m.record(1000)
        for _ in range(999):
            m.record(0)
        self.assertEqual(m.count(), 1000)
        self.assertEqual(m.mean(), 1.0)

    def test_old_sample_still_counts_after_many_new_ones(self):
        m = Meter()
        m.record(10)
        m.record(20)
        self.assertEqual(m.count(), 2)
        self.assertEqual(m.mean(), 15.0)

    def test_mean_changes_only_via_record_and_reset(self):
        m = Meter()
        m.record(4)
        first = m.mean()
        first_again = m.mean()
        self.assertEqual(first, first_again)
        m.record(8)
        self.assertEqual(m.mean(), 6.0)


class TestMeterReset(unittest.TestCase):
    def test_reset_clears_mean(self):
        m = Meter()
        m.record(9)
        m.reset()
        self.assertEqual(m.mean(), 0.0)

    def test_reset_clears_count_and_total(self):
        m = Meter()
        for v in (1, 2, 3):
            m.record(v)
        m.reset()
        self.assertEqual(m.count(), 0)
        self.assertEqual(m.total(), 0.0)

    def test_reset_only_affects_recorded_before_it(self):
        m = Meter()
        m.record(5)
        m.reset()
        m.record(1)
        self.assertEqual(m.count(), 1)
        self.assertEqual(m.mean(), 1.0)


class TestMeterRejectsBadInput(unittest.TestCase):
    def test_record_rejects_text(self):
        with self.assertRaises(TypeError):
            Meter().record("3")

    def test_record_rejects_none(self):
        with self.assertRaises(TypeError):
            Meter().record(None)

    def test_record_rejects_containers(self):
        with self.assertRaises(TypeError):
            Meter().record([1])

    def test_rejected_sample_does_not_change_state(self):
        m = Meter()
        m.record(2)
        with self.assertRaises(TypeError):
            m.record("not a number")
        self.assertEqual(m.count(), 1)
        self.assertEqual(m.mean(), 2.0)


if __name__ == "__main__":
    unittest.main()