"""RateController 的专项测试：反演、平滑、限幅、空窗不甩 1.0。"""

import unittest

from tracesamp.controller import RateController


class TestRateInversion(unittest.TestCase):
    def test_first_observation_inverts_rate_from_throughput(self):
        controller = RateController(target_per_sec=100.0)
        rate = controller.observe(0.0, 1000.0)
        self.assertAlmostEqual(rate, 0.1)
        self.assertEqual(controller.updates(), 1)

    def test_rate_equals_target_over_throughput_at_steady_state(self):
        controller = RateController(target_per_sec=200.0)
        rate = 1.0
        for _ in range(8):
            rate = controller.observe(8000.0 * rate, 8000.0)
        self.assertAlmostEqual(rate, 0.025, places=4)

    def test_low_traffic_clamps_to_full_rate(self):
        controller = RateController(target_per_sec=500.0)
        self.assertEqual(controller.observe(0.0, 100.0), 1.0)

    def test_min_rate_floor_is_respected(self):
        controller = RateController(target_per_sec=0.5, min_rate=0.001)
        controller.observe(0.0, 10000.0)
        self.assertEqual(controller.rate(), 0.001)

    def test_max_rate_ceiling_is_respected(self):
        controller = RateController(target_per_sec=100.0, max_rate=1.0)
        controller.observe(0.0, 10.0)
        self.assertEqual(controller.rate(), 1.0)


class TestNoThrash(unittest.TestCase):
    def test_zero_sampled_does_not_slam_to_max(self):
        # 旧实现的事故根因：一窗 sampled=0 就把采样率拽到 1.0
        controller = RateController(target_per_sec=100.0)
        controller.observe(0.0, 1000.0)
        self.assertAlmostEqual(controller.rate(), 0.1)
        # 哪怕这窗一条没采到（例如 trace 恰好都落在丢的区间），
        # 只要吞吐在，就不许跳 1.0
        rate = controller.observe(0.0, 1000.0)
        self.assertAlmostEqual(rate, 0.1)

    def test_idle_window_holds_rate(self):
        controller = RateController(target_per_sec=100.0)
        controller.observe(0.0, 1000.0)
        before = controller.rate()
        self.assertEqual(controller.observe(0.0, 0.0), before)
        self.assertEqual(controller.updates(), 1)

    def test_step_change_is_clamped(self):
        controller = RateController(target_per_sec=100.0)
        controller.observe(0.0, 1000.0)  # 0.1
        # 吞吐突然翻 100 倍：单步最多压 4 倍，不许一步钉地板
        rate = controller.observe(0.0, 100000.0)
        self.assertGreaterEqual(rate, 0.1 / 4.0 - 1e-9)
        # 吞吐突然掉到 1/100：单步最多抬 4 倍，不许一步甩天花板
        low = rate
        rate = controller.observe(0.0, 1000.0)
        self.assertLessEqual(rate, low * 4.0 + 1e-9)

    def test_recovery_does_not_get_stuck_at_floor(self):
        controller = RateController(target_per_sec=1.0, min_rate=0.001)
        controller.observe(0.0, 100000.0)
        controller.observe(0.0, 100000.0)
        self.assertAlmostEqual(controller.rate(), 0.001)
        # 高流量过去，吞吐恢复到 target 以下，几个 tick 内回到 1.0
        for _ in range(12):
            controller.observe(0.0, 0.5)
        self.assertEqual(controller.rate(), 1.0)


class TestSmoothing(unittest.TestCase):
    def test_small_wobble_is_absorbed(self):
        controller = RateController(target_per_sec=200.0)
        for _ in range(8):
            controller.observe(0.0, 2000.0)
        center = controller.rate()
        rates = []
        for _ in range(8):
            rates.append(controller.observe(0.0, 1900.0))
            rates.append(controller.observe(0.0, 2100.0))
        self.assertLess(max(rates) - min(rates), 0.03)
        self.assertLess(abs(center - 0.1), 0.005)

    def test_reset_forgets_history(self):
        controller = RateController(target_per_sec=100.0)
        controller.observe(0.0, 10000.0)
        self.assertNotEqual(controller.rate(), 1.0)
        controller.reset()
        self.assertEqual(controller.rate(), 1.0)
        self.assertEqual(controller.updates(), 0)
        rate = controller.observe(0.0, 500.0)
        self.assertAlmostEqual(rate, 0.2)


class TestValidation(unittest.TestCase):
    def test_bad_target(self):
        with self.assertRaises(ValueError):
            RateController(0.0)

    def test_bad_bounds(self):
        with self.assertRaises(ValueError):
            RateController(10.0, min_rate=0.0)
        with self.assertRaises(ValueError):
            RateController(10.0, min_rate=0.5, max_rate=0.2)
        with self.assertRaises(ValueError):
            RateController(10.0, max_rate=1.5)


if __name__ == "__main__":
    unittest.main()
