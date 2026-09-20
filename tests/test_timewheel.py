"""timewheel 语义测试：以 README 的语义约定为准逐条锁定，并与朴素参考实现对拍。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests
    python3 tests/test_timewheel.py

时序全部由注入的 ManualClock 定死，对拍使用固定 seed，可独立重复运行。
"""

import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from timewheel import TimeWheel
from timewheel.clock import ManualClock


def make_wheel(slots=8, tick=1.0, start=0.0):
    clock = ManualClock(start)
    wheel = TimeWheel(slots=slots, tick=tick, clock=clock)
    return wheel, clock


def go_to(wheel, clock, target):
    """把注入时钟拨到 target 并推进轮子，定死时序节奏。"""
    clock.advance(target - clock.t)
    wheel.advance(target)


class TestReadmeSemantics(unittest.TestCase):
    """README 语义约定中源码当前满足的部分（全绿）。"""

    def test_add_rejects_non_positive_delay(self):
        # README §1：delay 必须 > 0，否则 ValueError。
        wheel, _ = make_wheel()
        for bad in (0, -0.5, -3):
            with self.assertRaises(ValueError):
                wheel.add(bad, "x")

    def test_add_rejects_delay_beyond_one_revolution(self):
        # README §1：delay 不得超过一整圈 slots*tick；恰好一整圈合法。
        wheel, _ = make_wheel(slots=8, tick=1.0)
        with self.assertRaises(ValueError):
            wheel.add(8.5, "x")
        handle = wheel.add(8, "x")
        self.assertEqual(handle.deadline, 8.0)

    def test_advance_rejects_backwards(self):
        # README §2：now 小于当前时刻 → ValueError；相等则不报错、不推进。
        wheel, clock = make_wheel()
        go_to(wheel, clock, 2)
        with self.assertRaises(ValueError):
            wheel.advance(1.5)
        go_to(wheel, clock, 2)
        self.assertEqual(wheel.now, 2.0)

    def test_sub_tick_advance_does_not_move(self):
        # README §2：与当前时刻之差不足一个 tick → 不推进。
        wheel, clock = make_wheel()
        wheel.add(2, "x")
        go_to(wheel, clock, 0.9)
        self.assertEqual(wheel.now, 0.0)
        self.assertEqual(wheel.due(), [])
        go_to(wheel, clock, 2.0)
        self.assertEqual(wheel.due(), ["x"])

    def test_now_advances_in_whole_ticks(self):
        # README §1：内部时刻只随 advance 以整 tick 步进。
        wheel, clock = make_wheel()
        go_to(wheel, clock, 2.7)
        self.assertEqual(wheel.now, 2.0)
        go_to(wheel, clock, 2.9)
        self.assertEqual(wheel.now, 2.0)

    def test_due_returns_expiry_order_and_clears(self):
        # README §3：due 顺序「即到期先后」，返回后清空。
        # 同槽两个任务 real deadline 不同：先到期的先出。
        wheel, clock = make_wheel()
        wheel.add(2.9, "late-in-slot")   # deadline 2.9，落槽 3
        go_to(wheel, clock, 1)
        wheel.add(1.2, "early-in-slot")  # deadline 2.2，落槽 3
        go_to(wheel, clock, 3)
        self.assertEqual(wheel.due(), ["early-in-slot", "late-in-slot"])
        self.assertEqual(wheel.due(), [])

    def test_overdue_task_still_fires(self):
        # README §2：deadline 已过的任务照常触发（迟到不豁免）。
        wheel, clock = make_wheel()
        wheel.add(2, "x")
        go_to(wheel, clock, 10)
        self.assertEqual(wheel.due(), ["x"])

    def test_handles_are_independent(self):
        # README §4：add 返回的句柄彼此独立，取消一个不影响另一个。
        wheel, clock = make_wheel()
        h1 = wheel.add(1, "a")
        wheel.add(1, "b")
        wheel.cancel(h1)
        go_to(wheel, clock, 1)
        self.assertEqual(wheel.due(), ["b"])

    def test_cancel_in_slot_is_idempotent(self):
        # README §5：任务在槽中可取消；重复取消返回 False（幂等，不抛错）。
        wheel, clock = make_wheel()
        h = wheel.add(1, "x")
        self.assertTrue(wheel.cancel(h))
        self.assertFalse(wheel.cancel(h))
        self.assertFalse(h.cancel())
        go_to(wheel, clock, 2)
        self.assertEqual(wheel.due(), [])

    def test_cancel_after_due_returns_false(self):
        # README §5：任务已被 due() 取走后取消返回 False。
        wheel, clock = make_wheel()
        h = wheel.add(1, "x")
        go_to(wheel, clock, 1)
        self.assertEqual(wheel.due(), ["x"])
        self.assertFalse(wheel.cancel(h))

    def test_handle_cancel_delegates_to_wheel(self):
        wheel, clock = make_wheel()
        h = wheel.add(1, "x")
        self.assertTrue(h.cancel())
        go_to(wheel, clock, 1)
        self.assertEqual(wheel.due(), [])

    def test_advance_does_not_change_pending_deadline(self):
        # 推进过程本身不能改变已挂任务的到期时刻，也不能让其提前触发。
        wheel, clock = make_wheel()
        h = wheel.add(5, "x")
        self.assertEqual(h.deadline, 5.0)
        go_to(wheel, clock, 2)
        go_to(wheel, clock, 4)
        self.assertEqual(h.deadline, 5.0)
        self.assertEqual(wheel.due(), [])
        go_to(wheel, clock, 5)
        self.assertEqual(wheel.due(), ["x"])

    def test_small_steps_equal_one_big_step(self):
        # 多次小步推进与一次大步推进到同一时刻，触发序列完全一致。
        def run(chunks):
            wheel, clock = make_wheel()
            for i, d in enumerate([1, 2, 3, 4, 5, 6]):
                wheel.add(d, "t%d" % i)
            fired = []
            t = 0
            for c in chunks:
                t += c
                go_to(wheel, clock, t)
                fired.extend(wheel.due())
            return fired

        self.assertEqual(run([6]), run([1, 1, 1, 1, 1, 1]))
        self.assertEqual(run([6]), run([2, 3, 1]))


class TestPinnedDefects(unittest.TestCase):
    """源码与 README 不符的缺陷钉案（当前为红）。"""

    # 缺陷钉案：README §1 —— 槽下标以 slots 为模，「最后一个槽（下标 slots-1）
    # 照常参与回绕」；delay=7 在 8 槽轮上应落入槽 7，推进 7 个 tick 后到期触发。
    # 实际：源码按 mod (slots-1) 落槽，任务被错放进槽 0，advance(7) 后没有触发。
    def test_last_slot_participates_in_wraparound(self):
        wheel, clock = make_wheel(slots=8, tick=1.0)
        wheel.add(7, "x")
        go_to(wheel, clock, 7)
        self.assertEqual(wheel.due(), ["x"])

    # 缺陷钉案：README §1/§2 —— delay 恰为一整圈时 deadline = now + slots*tick，
    # 槽 (cursor + slots) mod slots = cursor，应当推进满一圈后才触发，不提前。
    # 实际：mod (slots-1) 使其落入槽 1，第一个 tick 就被提前触发。
    def test_full_revolution_delay_not_fired_early(self):
        wheel, clock = make_wheel(slots=8, tick=1.0)
        wheel.add(8, "y")
        go_to(wheel, clock, 1)
        self.assertEqual(wheel.due(), [])

    # 缺陷钉案：README §4 —— 相同 delay 的两次 add 是两个不同任务，到期都必须出现。
    # 实际：就绪队列用 deadline 作 dict key，同 deadline 的任务互相覆盖，只剩一个。
    def test_same_delay_adds_two_distinct_tasks(self):
        wheel, clock = make_wheel()
        wheel.add(2, "A")
        wheel.add(2, "B")
        go_to(wheel, clock, 2)
        self.assertEqual(wheel.due(), ["A", "B"])

    # 缺陷钉案：README §5 —— 任务已进入就绪队列但尚未被 due() 取走时，
    # cancel 仍应生效并返回 True。
    # 实际：cancel 只查找槽位，就绪队列中的任务取消失败（返回 False），
    # 且随后仍被 due() 取出。
    def test_cancel_ready_task(self):
        wheel, clock = make_wheel()
        h = wheel.add(1, "x")
        go_to(wheel, clock, 1)  # x 已进入就绪队列，尚未被 due 取走
        self.assertTrue(wheel.cancel(h))
        self.assertEqual(wheel.due(), [])

    # 缺陷钉案：README §2 —— 一次 advance 跨多个槽（含跨回绕点）时，被跨过的
    # 每个槽的任务都必须恰好进入就绪队列一次；deadline 已过的照常触发。
    # 这里 D 在 t=3 挂入（delay=6，deadline=9，应在槽 (3+6)%8=1），advance(9)
    # 跨回绕点经过槽 4..7,0,1，D 应在本次推进中触发。
    # 实际：D 未触发 —— 落槽取模错误（mod (slots-1) 落到槽 2）与回绕分支
    # 漏掉着陆槽（range(0, new_cursor) 不含 new_cursor）叠加导致。
    def test_wrapping_multi_slot_advance_fires_crossed_slots(self):
        wheel, clock = make_wheel(slots=8, tick=1.0)
        go_to(wheel, clock, 3)
        wheel.add(6, "D")
        go_to(wheel, clock, 9)
        self.assertEqual(wheel.due(), ["D"])


class RefWheel:
    """朴素参考实现：按到期时刻排序的列表，每次推进扫描到期项。

    时序语义基准：advance 单调推进时，每个任务恰好在其到期时刻（按整 tick
    量化）被触发一次，不早不晚不重复；多次小步与一次大步推进到同一时刻，
    触发序列完全一致。取消后的任务不再触发；推进不改变已挂任务的到期时刻。
    """

    def __init__(self, slots, tick, start):
        self.slots = slots
        self.tick = tick
        self.now = float(start)
        self._seq = 0
        self.pending = []  # 已挂未到期
        self.ready = []    # 已到期未取走

    def add(self, delay, task):
        if delay <= 0:
            raise ValueError("delay must be positive")
        if delay > self.slots * self.tick:
            raise ValueError("delay beyond one revolution")
        handle = {
            "eff": self.now + math.ceil(delay / self.tick) * self.tick,
            "deadline": self.now + delay,
            "seq": self._seq,
            "task": task,
            "cancelled": False,
            "collected": False,
        }
        self._seq += 1
        self.pending.append(handle)
        return handle

    def advance(self, now):
        if now < self.now:
            raise ValueError("timewheel cannot move backwards")
        steps = int((now - self.now) // self.tick)
        if steps <= 0:
            return
        self.now += steps * self.tick
        firing = [h for h in self.pending if h["eff"] <= self.now]
        self.pending = [h for h in self.pending if h["eff"] > self.now]
        firing.sort(key=lambda h: (h["deadline"], h["seq"]))
        self.ready.extend(firing)

    def due(self):
        out = [h["task"] for h in self.ready]
        for h in self.ready:
            h["collected"] = True
        self.ready = []
        return out

    def cancel(self, handle):
        if handle["cancelled"] or handle["collected"]:
            return False
        handle["cancelled"] = True
        for queue in (self.pending, self.ready):
            if handle in queue:
                queue.remove(handle)
                break
        return True


class TestReferenceFuzz(unittest.TestCase):
    # 对拍：固定 seed 随机交错 挂载/取消/推进/取走，触发顺序、触发次数、
    # cancel 返回值、内部时刻、最终剩余任务都必须与参考实现一致。
    # 当前为红：暴露出与上面钉案相同的出入（落槽取模错误、就绪队列按
    # deadline 去重、就绪任务不可取消）。
    def test_fuzz_against_reference(self):
        rng = random.Random(20260920)
        slots, tick = 8, 1.0
        wheel, clock = make_wheel(slots=slots, tick=tick)
        ref = RefWheel(slots, tick, 0.0)
        handles = []
        for i in range(400):
            op = rng.random()
            if op < 0.45:
                delay = rng.choice([0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8,
                                    8.5, 0, -1])
                task = "t%d" % i
                wheel_handle = ref_handle = None
                wheel_exc = ref_exc = False
                try:
                    wheel_handle = wheel.add(delay, task)
                except ValueError:
                    wheel_exc = True
                try:
                    ref_handle = ref.add(delay, task)
                except ValueError:
                    ref_exc = True
                self.assertEqual(wheel_exc, ref_exc,
                                 "add 异常行为不一致, op=%d delay=%r" % (i, delay))
                if wheel_handle is not None:
                    handles.append((wheel_handle, ref_handle))
            elif op < 0.65 and handles:
                wheel_handle, ref_handle = rng.choice(handles)
                self.assertEqual(wheel.cancel(wheel_handle), ref.cancel(ref_handle),
                                 "cancel 返回值不一致, op=%d" % i)
            elif op < 0.9:
                clock.advance(rng.choice([0.3, 0.5, 1, 1.5, 2, 3, 5, 8, 13, 21]))
                wheel.advance(clock.t)
                ref.advance(clock.t)
                self.assertEqual(wheel.now, ref.now,
                                 "内部时刻不一致, op=%d" % i)
            else:
                self.assertEqual(wheel.due(), ref.due(),
                                 "due 序列不一致, op=%d" % i)
        # 最终大步推进清空轮子，比较剩余任务。
        clock.advance(1000)
        wheel.advance(clock.t)
        ref.advance(clock.t)
        self.assertEqual(wheel.due(), ref.due(), "最终 due 序列不一致")
        remaining_wheel = sorted(h.task for b in wheel._buckets for h in b)
        remaining_ref = sorted(h["task"] for h in ref.pending)
        self.assertEqual(remaining_wheel, remaining_ref, "最终剩余任务不一致")


if __name__ == "__main__":
    unittest.main()
