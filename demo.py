"""resumex 演示：基线按批推送 + 双源合流续传、乱序窗口、损坏回退、分路背压。"""

import os
import tempfile

from resumex.resume import BackpressureSink, MergedStreamRunner, WatermarkStore
from resumex.stream import MemorySink, MemorySource, StreamRunner


def main():
    print("=== 按批推送（每批 3 条） ===")
    source = MemorySource([(seq, "订单-%03d" % seq) for seq in range(1, 8)])
    sink = MemorySink()
    runner = StreamRunner(source, sink, batch_size=3)
    moved = runner.run()
    for record in sink.received():
        print("  seq=%d payload=%r" % (record.seq, record.payload))
    progress = runner.progress()
    print("  本次推送 %d 条，下游水位 %d" % (moved, sink.watermark))
    print(
        "  进度: last_seq=%d pushed=%d batches=%d"
        % (progress["last_seq"], progress["pushed"], progress["batches"])
    )

    with tempfile.TemporaryDirectory() as tmp:
        wm_path = os.path.join(tmp, "watermark.log")

        print("=== 双源合流 + 落盘续传 ===")
        src_a = MemorySource([(1, "A-1"), (3, "A-3"), (5, "A-5")])
        src_b = MemorySource([(2, "B-2"), (4, "B-4"), (6, "B-6")])
        snk_a, snk_b = BackpressureSink(), BackpressureSink()

        def make_runner():
            return MergedStreamRunner(
                {"a": src_a, "b": src_b},
                {"a": snk_a, "b": snk_b},
                wm_path,
                batch_size=2,
                window=3,
            )

        make_runner().run()
        print("  首跑后: a=%s b=%s" % (
            [r.seq for r in snk_a.received()], [r.seq for r in snk_b.received()]
        ))
        src_a.append(7, "A-7")
        src_b.append(8, "B-8")
        make_runner().run()  # 同一份水位，模拟重启
        merged = sorted(r.seq for r in snk_a.received() + snk_b.received())
        print("  重启续推后合并序号: %s（无重复）" % merged)

        print("=== 乱序窗口（窗口=3，全局水位 8） ===")
        window_path = os.path.join(tmp, "window.log")
        ahead = MemorySource([(seq, "主线-%d" % seq) for seq in range(1, 9)])
        src_c = MemorySource()
        snk_c = BackpressureSink()

        def window_runner():
            return MergedStreamRunner(
                {"a": ahead, "c": src_c},
                {"a": BackpressureSink(), "c": snk_c},
                window_path,
                batch_size=3,
                window=3,
            )

        window_runner().run()  # 先把全局水位推到 8
        src_c.append(2, "超窗-2")
        src_c.append(6, "迟到-6")
        runner = window_runner()
        runner.run()
        p = runner.progress()
        print("  下游收到: %s" % [r.seq for r in snk_c.received()])
        print("  窗口内补入=%d 超窗丢弃=%d" % (p["late_accepted"], p["dropped"]))

        print("=== 水位文件损坏：退回最后一个完好点 ===")
        with open(window_path, "ab") as handle:
            handle.write(b"rx1|c|99|0.0|deadbeef")  # 模拟半截写入
        store = WatermarkStore(window_path, ["a", "c"])
        print("  回退后水位: a=%d c=%d，修复次数=%d" % (
            store.position("a"), store.position("c"),
            store.stats()["repairs"],
        ))

        print("=== 分路背压：a 路下游慢，只停 a 路 ===")
        bp_path = os.path.join(tmp, "bp.log")
        slow_a = MemorySource([(1, "A-1"), (3, "A-3")])
        fast_b = MemorySource([(2, "B-2"), (4, "B-4")])
        slow_sink, fast_sink = BackpressureSink(), BackpressureSink()
        slow_sink.set_blocked(True)
        runner = MergedStreamRunner(
            {"a": slow_a, "b": fast_b},
            {"a": slow_sink, "b": fast_sink},
            bp_path,
            batch_size=2,
            window=10,
        )
        runner.run()
        print("  阻塞期间: a 收到=%s b 收到=%s 阻塞计数=%s" % (
            [r.seq for r in slow_sink.received()],
            [r.seq for r in fast_sink.received()],
            runner.progress()["blocked"],
        ))
        slow_sink.set_blocked(False)
        MergedStreamRunner(
            {"a": slow_a, "b": fast_b},
            {"a": slow_sink, "b": fast_sink},
            bp_path,
            batch_size=2,
            window=10,
        ).run()
        print("  恢复后:   a 收到=%s" % [r.seq for r in slow_sink.received()])


if __name__ == "__main__":
    main()
