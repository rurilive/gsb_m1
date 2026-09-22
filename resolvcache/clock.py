"""时钟源。

生产用单调时钟，测试与对拍注入可以手动推进的时钟。
缓存内部所有"现在"都必须来自这里，不许直接调 time。
"""

import threading
import time


class SystemClock:
    """默认时钟，转发 time.monotonic。"""

    def __call__(self):
        return time.monotonic()


class ManualClock:
    """手动时钟，读数在所有线程间共享，只有显式调用才会前进。

    advance 按秒推进；set 直接改写读数，用来模拟对时回拨。
    """

    def __init__(self, start=0.0):
        self._lock = threading.Lock()
        self._now = float(start)

    def __call__(self):
        with self._lock:
            return self._now

    def advance(self, seconds):
        if seconds < 0:
            raise ValueError("advance 只接受非负秒数，回拨请用 set")
        with self._lock:
            self._now += float(seconds)
            return self._now

    def set(self, value):
        with self._lock:
            self._now = float(value)
            return self._now
