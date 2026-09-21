"""resumex 演示。

1. 单路基线：按批推送，看进度。
2. 双源合并：两路各推各的，窗口内迟到补入、超窗丢弃并计数。
3. 重启续传：同一份水位文件新建搬运器，从水位接着推，不重喂。
4. 分路背压：一路下游慢只停一路，另一路照推，恢复后迟到补齐。
5. 水位判废：半截行拒绝、整份损坏退回上一个完好点。
"""

import os
import tempfile

from resumex.resume import BackpressureGate, MergeRunner, WatermarkStore
from resumex.stream import MemorySink, MemorySource, StreamRunner


def show(title, sink, stats=None):
    print("=== %s ===" % title)
    print("  下游收到: %s" % [r.seq for r in sink.received()])
    if stats is not None:
        print(
            "  累计补入迟到 %d 条、超窗丢弃 %d 条、重复 %d 条，全局水位 %d"
            % (
                stats["late_accepted"],
                stats["late_dropped"],
                stats["duplicates"],
                stats["global_watermark"],
            )
        )


def demo_single_stream():
    print("=== 单路基线：按批推送（每批 3 条） ===")
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


def demo_merge_and_window(workdir):
    path = os.path.join(workdir, "watermark")
    sources = {
        "A": MemorySource([(1, "A-1"), (3, "A-3"), (5, "A-5"),
                           (7, "A-7"), (9, "A-9")]),
        "B": MemorySource([(2, "B-2"), (4, "B-4")]),
    }
    sink = MemorySink()
    runner = MergeRunner(sources, sink, WatermarkStore(path),
                         window=3, batch_size=2)
    runner.run()
    show("双源合并：两路按各自水位取数（窗口 W=3）", sink, runner.stats())
    print("  分路水位落盘: %s" % runner.stats()["positions"])

    # B 路后来才推到：8 在窗口内（9-3<=8）补入；5 已超窗丢弃。
    sources["B"].append(5, "B-5-too-late")
    sources["B"].append(8, "B-8-late")
    runner.run()
    show("迟到到达：8 窗口内补入，5 超窗丢弃", sink, runner.stats())
    return path


def demo_restart(path):
    # 全新来源（含全部历史）+ 全新搬运器，只共用同一份水位文件。
    sources = {
        "A": MemorySource([(1, "A-1"), (3, "A-3"), (5, "A-5"),
                           (7, "A-7"), (9, "A-9"), (11, "A-11")]),
        "B": MemorySource([(2, "B-2"), (4, "B-4"), (5, "B-5-too-late"),
                           (8, "B-8-late"), (10, "B-10")]),
    }
    sink = MemorySink()
    runner = MergeRunner(sources, sink, WatermarkStore(path),
                         window=3, batch_size=2)
    runner.run()
    show("重启续传：各按水位之后取数，1~9 不重喂", sink, runner.stats())


def demo_backpressure(workdir):
    sources = {
        "A": MemorySource([(1, "A-1"), (3, "A-3"), (5, "A-5")]),
        "B": MemorySource([(2, "B-2"), (4, "B-4")]),
    }
    gate_b = BackpressureGate()
    gate_b.close()  # B 路下游慢，先闸住
    sink = MemorySink()
    runner = MergeRunner(
        sources, sink,
        WatermarkStore(os.path.join(workdir, "wm-backpressure")),
        window=5, batch_size=2, gates={"B": gate_b},
    )
    runner.run()
    show("分路背压：只闸 B 路，A 路照推", sink, runner.stats())
    print("  B 路阻塞轮次 %d，A 路阻塞轮次 %d"
          % (runner.stats()["gates"]["B"]["blocked_rounds"],
             runner.stats()["gates"]["A"]["blocked_rounds"]))

    gate_b.open()  # B 路下游恢复，2、4 在窗口内按迟到补齐
    runner.run()
    show("B 路恢复：停取期间的数据在窗口内补齐", sink, runner.stats())


def demo_corrupted_watermark(path):
    # 半截行：主文件尾巴写坏一半，该行判废，其余行照用。
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("B|99|deadbe")
    torn = WatermarkStore(path)
    print("=== 半截水位行判废 ===")
    print("  判废 %d 行，水位仍是 %s，取自 %s"
          % (torn.stats()["rejected_lines"], torn.positions(),
             torn.last_recovery()[0]))
    torn.commit()

    # 整份崩坏：主文件头都没了，退回 .bak 的上一个完好点。
    good = torn.positions()
    torn.commit({"A": 40, "B": 40})  # 让 .bak 与主文件不同，便于看出回退
    with open(path, "wb") as handle:
        handle.write(b"\x00\x00garbage-no-magic")
    recovered = WatermarkStore(path)
    print("=== 水位文件损坏：退回上一个完好点 ===")
    print("  完好点水位 %s，损坏后恢复为 %s（fallback=%d）"
          % (good, recovered.positions(), recovered.stats()["fallbacks"]))


def main():
    workdir = tempfile.mkdtemp(prefix="resumex-demo-")
    print("水位目录: %s\n" % workdir)
    demo_single_stream()
    print()
    path = demo_merge_and_window(workdir)
    print()
    demo_restart(path)
    print()
    demo_backpressure(workdir)
    print()
    demo_corrupted_watermark(path)
    print("\n水位文件保留在: %s（可自行查看 watermark / watermark.bak）" % workdir)


if __name__ == "__main__":
    main()
