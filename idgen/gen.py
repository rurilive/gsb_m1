"""本地 ID 生成器：毫秒时间戳左移 16 位后拼自增计数。"""
import threading
import time

COUNTER_BITS = 16
COUNTER_MASK = (1 << COUNTER_BITS) - 1
EPOCH_MS = 1700000000000


class IdGenerator:
    def __init__(self, clock=time.time):
        self._clock = clock
        self._lock = threading.Lock()
        self._last_ms = 0
        self._counter = 0

    def _now_ms(self):
        return int(self._clock() * 1000)

    def next_id(self):
        with self._lock:
            ms = self._now_ms()
            if ms > self._last_ms:
                self._last_ms = ms
                self._counter = 0
            else:
                self._counter += 1
            return ((ms - EPOCH_MS) << COUNTER_BITS) | self._counter
