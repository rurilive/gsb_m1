"""pipeflow 现状演示。

第一段：逐条处理的 run_stream，把记录变换后累加。
第二段：可组合的批处理管道，含 Batch 与超时冲刷（见下方实现）。
"""

from pipeflow import (
    Batch,
    CollectSink,
    Filter,
    IterSource,
    Map,
    Pipeline,
    Source,
    run_stream,
)


class FakeClock:
    """可手动推进的假时钟，用来演示 Batch 的超时冲刷。"""

    def __init__(self, t=0.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def main():
    print("=== 逐条处理 ===")
    total = run_stream(
        range(1, 6), lambda r: r * r, lambda acc, v: acc + v, initial=0
    )
    print(f"  1 到 5 的平方和 = {total}")

    print("=== 批处理管道 ===")
    clock = FakeClock()
    batches = []

    def record_batch(batch):
        batches.append(list(batch))
        return batch

    sink = CollectSink()
    pipeline = Pipeline(
        IterSource(range(1, 11)),
        [
            Map(lambda x: x * 10),
            Filter(lambda x: x % 20 != 0),
            Batch(3, batch_func=record_batch),
        ],
        sink,
        capacity=4,
        clock=clock,
    )
    stats = pipeline.run()
    print(f"  按条数冲刷的批 = {batches}")
    print(f"  sink 收到 {sink.items}")
    print(f"  统计 {stats}")

    print("=== 超时冲刷 ===")
    slow_clock = FakeClock()

    class SlowSource(Source):
        def iter_items(self):
            for i in range(6):
                slow_clock.advance(0.6)
                yield i

    groups = []

    def collect(batch):
        groups.append(list(batch))
        return batch

    slow_sink = CollectSink()
    Pipeline(
        SlowSource(),
        [Batch(4, batch_func=collect, timeout=1.0)],
        slow_sink,
        clock=slow_clock,
        capacity=4,
    ).run()
    print(f"  每 0.6 秒一条，超时 1.0 秒触发的批 = {groups}")


if __name__ == "__main__":
    main()