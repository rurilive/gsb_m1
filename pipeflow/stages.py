"""算子抽象与统计。

现状只有 run_stream（见 core.py）这一个逐条处理入口，没有任何算子抽象。
本模块给出 Source、Map、Filter、FlatMap、Batch、Sink，以及承载它们产出的
记录壳与统计。算子本身只声明自己的处理逻辑，记录如何在有界队列之间搬运由
Pipeline 负责；算子之间统一以 _Record 壳交互，壳上带记录进入管道时的时刻，
Batch 用它判定一批是否已经超时。
"""


class StageStats:
    """一次运行的计数：穿过整条管道的、被跳过的、最终失败的。"""

    __slots__ = ("processed", "skipped", "failed")

    def __init__(self, processed=0, skipped=0, failed=0):
        self.processed = processed
        self.skipped = skipped
        self.failed = failed

    def __repr__(self):
        return (
            f"StageStats(processed={self.processed}, "
            f"skipped={self.skipped}, failed={self.failed})"
        )


class _Record:
    """队列里搬运的壳：包住用户记录，带上它进入管道时的时刻。"""

    __slots__ = ("value", "entered")

    def __init__(self, value, entered):
        self.value = value
        self.entered = entered


class Source:
    """数据源头：提供数据并知道何时结束。

    子类实现 iter_items，逐条产出原始记录；迭代自然结束即源头结束。
    """

    def iter_items(self):
        raise NotImplementedError


class IterSource(Source):
    """把可迭代对象包装成源头。"""

    def __init__(self, items):
        self._items = items

    def iter_items(self):
        return iter(self._items)


class Stage:
    """算子基类。

    每条记录都以 _Record 壳传入 process，返回零条、一条或多条用户记录。
    空返回表示这条被吞掉。
    """

    def process(self, record):
        raise NotImplementedError

    @staticmethod
    def _unwrap(record):
        return record.value if isinstance(record, _Record) else record


class Map(Stage):
    """逐条变换：一条进，一条出。"""

    def __init__(self, func):
        if not callable(func):
            raise TypeError("func must be callable")
        self.func = func

    def process(self, record):
        return [self.func(self._unwrap(record))]


class Filter(Stage):
    """逐条筛选：谓词为真才留下。"""

    def __init__(self, predicate):
        if not callable(predicate):
            raise TypeError("predicate must be callable")
        self.predicate = predicate

    def process(self, record):
        value = self._unwrap(record)
        return [value] if self.predicate(value) else []


class FlatMap(Stage):
    """把一条展开成零条或多条。"""

    def __init__(self, func):
        if not callable(func):
            raise TypeError("func must be callable")
        self.func = func

    def process(self, record):
        out = self.func(self._unwrap(record))
        return list(out) if out is not None else []


class Batch(Stage):
    """攒批算子：攒够 batch_size 条或超过 timeout 秒就冲刷。

    - batch_size 为正整数
    - batch_func 可选，收一个记录列表，返回一个记录列表（批内顺序即攒入
      顺序），返回结果逐条向下游发出；不传则原样逐条发出
    - timeout 为 None 表示只按条数冲刷；否则以记录上的到达时刻为准：一批自
      第一条进入起计时，下一条到达时若已间隔到 timeout，就先把旧批冲出再
      开新批。时刻来自注入的时钟，在源头逐条盖上，沿队列带到下游，判定只
      依赖记录自己的时刻，因而与线程调度无关
    - flush() 立即冲刷当前残留（空批不发）
    """

    def __init__(self, batch_size, batch_func=None, timeout=None):
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        if batch_func is not None and not callable(batch_func):
            raise TypeError("batch_func must be callable")
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
                raise ValueError("timeout must be a number or None")
            if timeout < 0:
                raise ValueError("timeout must not be negative")
        self.batch_size = batch_size
        self.batch_func = batch_func
        self.timeout = timeout
        self._buf = []
        self._first_entered = None

    @property
    def pending(self):
        return len(self._buf)

    def process(self, record):
        entered = record.entered if isinstance(record, _Record) else None
        out = []
        if (
            self._buf
            and self.timeout is not None
            and entered is not None
            and self._first_entered is not None
            and entered - self._first_entered >= self.timeout
        ):
            out.extend(self._flush_now())
        if not self._buf:
            self._first_entered = entered
        self._buf.append(self._unwrap(record))
        if len(self._buf) >= self.batch_size:
            out.extend(self._flush_now())
        return out

    def flush(self):
        """强制冲刷，返回发出的记录列表（空批返回空列表）。"""
        if not self._buf:
            return []
        return self._flush_now()

    def _flush_now(self):
        batch = self._buf
        self._buf = []
        self._first_entered = None
        if self.batch_func is not None:
            out = self.batch_func(list(batch))
            return list(out) if out is not None else []
        return list(batch)


class Sink:
    """管道终点：消费记录。子类实现 consume。"""

    def consume(self, value):
        raise NotImplementedError


class CollectSink(Sink):
    """把收到的记录按序收进一个列表，方便断言。"""

    def __init__(self):
        self.items = []

    def consume(self, value):
        self.items.append(value)