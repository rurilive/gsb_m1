"""朴素定时器 SimpleTimer：手动推进一拍，取走到期任务。

当前实现把待触发的任务全部放进一个列表，元素是绝对到期时刻与名字，每次
推进都要从头到尾线性扫描一遍找出到期项，取消也要逐个比对剔除。功能正确，
但推进的代价随任务总量线性增长，也没有分层结构或多级级联。
"""


class TimerError(ValueError):
    """定时器相关错误的基类。

    继承 ValueError，基线对非法入参的取值错误与后续实现抛出的定时器错误
    都能被同一个 except ValueError 捕获。
    """


def _next_due():
    """约定值：无待触发任务时 peek 返回它。"""
    return None


class SimpleTimer:
    """最朴素的定时器：一个列表装全部任务。

    - SimpleTimer()：时钟从零起步，一拍即一个整数时刻
    - add_at(delay, name)：把到期时刻记为时钟加延迟，追加到表尾
    - advance(n)：把时钟推进 n 拍，返回本次触发的名字列表
    - peek()：返回下一个到期时刻，无任务时返回约定值 None
    - cancel(name)：取消未到期的任务，找不到返回 False

    任务以 (到期时刻, 插入序, 名字) 保存；插入序就是列表下标，用来在同刻
    时保持先来先触发的顺序。
    """

    def __init__(self):
        self._now = 0
        self._tasks = []
        self._seq = 0

    @property
    def now(self):
        return self._now

    @property
    def size(self):
        return len(self._tasks)

    def add_at(self, delay, name):
        if not isinstance(delay, int) or isinstance(delay, bool):
            raise TimerError("delay must be an int")
        if delay < 0:
            raise TimerError("delay must not be negative")
        due = self._now + delay
        self._tasks.append((due, self._seq, name))
        self._seq += 1
        return name

    def advance(self, n):
        if not isinstance(n, int) or isinstance(n, bool):
            raise TimerError("n must be an int")
        if n < 0:
            raise TimerError("n must not be negative")
        fired = []
        for _ in range(n):
            self._now += 1
            due = [t for t in self._tasks if t[0] <= self._now]
            rest = [t for t in self._tasks if t[0] > self._now]
            due.sort(key=lambda t: (t[0], t[1]))
            self._tasks = rest
            fired.extend(t[2] for t in due)
        return fired

    def peek(self):
        if not self._tasks:
            return None
        return min(t[0] for t in self._tasks)

    def cancel(self, name):
        for i, t in enumerate(self._tasks):
            if t[2] == name:
                del self._tasks[i]
                return True
        return False
