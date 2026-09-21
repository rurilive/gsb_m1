"""resumex 现状演示。

第一段：来源放几条记录，搬运器按批推给下游，看进度。
第二段：预留的断点续传与水位演示位子（见文末注释）。
"""

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

    # TODO(续传改造): 水位落盘与去重实现后，在这里加一段演示：
    # 推送一批后把确认水位落盘，用同一份水位新建搬运器模拟重启，
    # 展示从水位接着推、下游对重复与乱序记录的丢弃计数，以及
    # 半截水位记录被拒后水位停在上一处完好值。


if __name__ == "__main__":
    main()
