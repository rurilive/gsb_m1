"""evokit 现状演示。

第一段：追加几条事件，看全量重放得到的当前状态与事件流版本。
第二段：预留的快照与并发控制演示位子（见文末注释）。
"""

from evokit.aggregate import Aggregate


def main():
    print("=== 追加事件与全量重放（现有能力） ===")
    agg = Aggregate()
    agg.append("created", {"field": "name", "value": "order-1"})
    agg.append("amount_set", {"field": "amount", "value": 100})
    agg.append("amount_set", {"field": "amount", "value": 250})
    print(f"  version   -> {agg.version}")
    print(f"  state     -> {agg.state}")
    print(f"  replay()  -> {agg.replay()}")
    print(f"  events    -> {[(e.version, e.etype) for e in agg.events()]}")

    # TODO(快照与增量重放): 快照能力实现后，在这里加一段演示：
    # 构造 Aggregate(snapshot_every=2)，追加若干事件触发自动快照，
    # 打印快照版本与增量重放只回放了哪几条事件。

    # TODO(乐观并发与损坏回退): 版本冲突检测与损坏回退实现后，在这里加一段演示：
    # 用 append(..., expected_version=...) 触发 ConcurrencyError，
    # 再把某条快照标记损坏，看 replay 回退到从头重放得到的相同状态。


if __name__ == "__main__":
    main()
