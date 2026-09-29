"""可组合、有背压的批处理管道。

Pipeline 把一个 Source、若干中间算子和一个 Sink 串起来，算子之间用有界队列
连接。队列写满时上游阻塞等待，下游取走一条腾出位子再把队首交给它；上游不会
在被阻塞期间多读一条，慢下游的进度反过来压住上游的产出，因此不会无限堆积。

run() 起一组后台线程逐段搬运记录，主线程等它们全部结束再汇总统计。每条记录
在源头盖上产生时刻（来自注入的时钟，默认 time.monotonic），时刻随记录一路带
到下游，Batch 用它判定一批是否已经超时。把时刻钉在产生点上，超时判定只依赖
记录看到的时刻，不依赖线程调度，因而确定。

任一环节以 abort 策略抛错时，停止标志被点亮，所有阻塞在满队列上的上游立刻
醒来收工，不会互相卡住；原始异常最终由 run() 抛给调用方，不被吞掉。
"""

import threading
import time
from collections import deque

from .stages import Batch, StageStats, _Record

_STOP = object()


class QueueFull(Exception):
    """保留了显式失败的类型：当前实现走阻塞，不做丢弃。"""


def _validate_capacity(capacity):
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
        raise ValueError("capacity must be a positive integer")
    return capacity


def _validate_policy(policy, retries):
    if policy not in ("skip", "retry", "abort"):
        raise ValueError("policy must be one of 'skip', 'retry', 'abort'")
    if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
        raise ValueError("retries must be a non-negative integer")
    return policy


def _validate_timeout(timeout):
    if timeout is not None and (
        not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
    ):
        raise ValueError("timeout must be a number or None")
    if timeout is not None and timeout < 0:
        raise ValueError("timeout must not be negative")
    return timeout


class Pipeline:
    """Source 接若干中间算子再接 Sink 的管道。

    - 有界队列容量由 capacity 给出，正整数，非法值在构造时 fail fast
    - 单条记录的处理异常按 policy 处置：skip 跳过并计入 skipped；retry 重试
      至多 retries 次，其间累计耗时超过 timeout 就停手，始终没救回来的计入
      failed；abort 立即停下并向外抛出该异常
    - run() 只跑一次，重复 run 抛 RuntimeError，返回 StageStats
    """

    def __init__(
        self,
        source,
        stages=None,
        sink=None,
        capacity=64,
        policy="abort",
        retries=0,
        timeout=None,
        clock=None,
    ):
        self.capacity = _validate_capacity(capacity)
        self.policy = _validate_policy(policy, retries)
        self.retries = retries
        self.timeout = _validate_timeout(timeout)
        self.clock = clock or time.monotonic
        self.source = source
        self.stages = list(stages or [])
        self.sink = sink
        self._ran = False

    def add(self, stage):
        """链式追加一个中间算子，返回自身。"""
        self.stages.append(stage)
        return self

    # -- 运行 -----------------------------------------------------------

    def run(self):
        if self._ran:
            raise RuntimeError("pipeline can only be run once")
        self._ran = True

        stats = StageStats()
        n = len(self.stages)
        queues = [deque() for _ in range(n + 1)]
        conds = [threading.Condition() for _ in range(n + 1)]
        done = [False] * (n + 1)  # done[i] 为真表示 queue[i] 不会再被写入
        stopping = threading.Event()
        error = [None]

        def push(qi, record):
            with conds[qi]:
                while len(queues[qi]) >= self.capacity:
                    if stopping.is_set():
                        return False
                    conds[qi].wait()
                queues[qi].append(record)
                conds[qi].notify_all()
                return True

        def pop(qi):
            with conds[qi]:
                while True:
                    if queues[qi]:
                        record = queues[qi].popleft()
                        conds[qi].notify_all()
                        return record
                    if done[qi] or stopping.is_set():
                        return _STOP
                    conds[qi].wait()

        def finish_writing(qi):
            with conds[qi]:
                done[qi] = True
                conds[qi].notify_all()

        def wake_all():
            stopping.set()
            for cond in conds:
                with cond:
                    cond.notify_all()

        def emit(qi, values):
            for value in values:
                if not push(qi, value):
                    return

        def resolve_failure(stage, record):
            """policy 非 abort 时处置一条失败的记录。

            返回 (handled, out)：handled 为真且 out 非空表示重试后拿到结果；
            handled 为真且 out 为空表示这条已在计数里了结；handled 为假表示
            需要向外抛出（abort）。
            """
            if self.policy == "skip":
                stats.skipped += 1
                return True, None
            # retry：至多 retries 次，累计耗时超过 timeout 就停手
            started = self.clock()
            for _ in range(self.retries):
                if self.timeout is not None and self.clock() - started >= self.timeout:
                    break
                try:
                    return True, stage.process(record)
                except Exception:
                    continue
            stats.failed += 1
            return True, None

        def stage_worker(wid):
            stage = self.stages[wid]
            try:
                while True:
                    record = pop(wid)
                    if record is _STOP:
                        if isinstance(stage, Batch):
                            emit(wid + 1, [_Record(v, self.clock()) for v in stage.flush()])
                        break
                    try:
                        out = stage.process(record)
                    except Exception:
                        if self.policy == "abort":
                            raise
                        _handled, out = resolve_failure(stage, record)
                    if out:
                        emit(wid + 1, [_Record(v, record.entered) for v in out])
            except Exception as exc:
                error[0] = exc
                wake_all()
            finally:
                finish_writing(wid + 1)

        def source_worker():
            try:
                for item in self.source.iter_items():
                    if stopping.is_set():
                        break
                    if not push(0, _Record(item, self.clock())):
                        break
            except Exception as exc:
                error[0] = exc
                wake_all()
            finally:
                finish_writing(0)

        def sink_worker():
            try:
                while True:
                    record = pop(n)
                    if record is _STOP:
                        break
                    self.sink.consume(record.value)
                    stats.processed += 1
            except Exception as exc:
                error[0] = exc
                wake_all()
            finally:
                finish_writing(n)

        threads = [threading.Thread(target=source_worker, name="pipeflow-source")]
        for wid in range(n):
            threads.append(
                threading.Thread(
                    target=stage_worker, args=(wid,), name=f"pipeflow-stage-{wid}"
                )
            )
        threads.append(threading.Thread(target=sink_worker, name="pipeflow-sink"))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        if error[0] is not None:
            raise error[0]
        return stats