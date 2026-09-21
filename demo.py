"""msglz 现状演示。

第一段：造一小批总线短消息，逐条独立压缩，看看每条的编码尺寸。
第二段：同一批语料训出预共享字典，对比带字典与不带字典的实测比率。
"""

import random
import tempfile

from msglz import DictStore, MessageCodec

#: 语料里时间戳的起点，固定住好复现。
BASE_TS = 1758300000

LEVELS = ["INFO", "WARN", "ERROR"]

ACTIONS = [
    "order.created",
    "order.paid",
    "order.shipped",
    "cart.updated",
    "user.login",
    "user.logout",
    "payment.retry",
    "inventory.sync",
]

NODES = ["cn-hangzhou-3", "cn-shanghai-1", "cn-beijing-2", "ap-singapore-1"]


def make_corpus(count=200, seed=7):
    """造一批像样的总线短消息：字段名固定，取值每次都换。

    同一批语料换个种子就是另一拨流量，训练和验收都拿它当样本。
    """
    rnd = random.Random(seed)
    messages = []
    for i in range(count):
        stamp = BASE_TS + i * rnd.randint(1, 9)
        hour = (stamp // 3600) % 24
        minute = (stamp // 60) % 60
        second = stamp % 60
        line = "2026-09-21T%02d:%02d:%02dZ %s %s id=%d user=u%d amount=%.2f node=%s" % (
            hour,
            minute,
            second,
            rnd.choice(LEVELS),
            rnd.choice(ACTIONS),
            rnd.randrange(100000, 999999),
            rnd.randrange(1000, 9999),
            rnd.randrange(100, 9900) / 100.0,
            rnd.choice(NODES),
        )
        if rnd.random() < 0.3:
            line += " trace=%08x" % rnd.randrange(1 << 32)
        if rnd.random() < 0.2:
            line += " note=%s" % "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6))
        messages.append(line.encode("ascii"))
    return messages


def main():
    corpus = make_corpus()
    codec = MessageCodec()
    encoded = [codec.encode(message) for message in corpus]
    raw = sum(len(m) for m in corpus)
    packed = sum(len(b) for b in encoded)
    print("=== 逐条独立压缩 %d 条短消息 ===" % len(corpus))
    print("  原文共 %d 字节，编码后共 %d 字节，比率 %.3f" % (raw, packed, packed / raw))
    print("  第一条：%d 字节 -> %d 字节" % (len(corpus[0]), len(encoded[0])))
    print("  样张：%s" % corpus[0][:64].decode("ascii"))

    print("=== 抽样解回 ===")
    for index in (0, 5, 20, 77):
        got = codec.decode(encoded[index])
        if got != corpus[index]:
            raise SystemExit("第 %d 条解出来跟原文不一致" % index)
        print("  #%d %d 字节 -> %d 字节，解回逐字节一致" % (
            index, len(corpus[index]), len(encoded[index])))

    st = codec.stats()
    print("=== 统计 ===")
    print("  消息数=%d 解码数=%d 比率=%.3f" % (
        st["messages"], st["decoded"], st["ratio"]))

    print("=== 预共享字典 ===")
    with tempfile.TemporaryDirectory() as store_dir:
        store = DictStore(store_dir, max_versions=3, min_gain=0.05)
        report = store.rollout(corpus)
        print("  训练 %d 条样本耗时 %.2f 秒，字典 %d 字节" % (
            report["samples"], report["train_seconds"], report["dict_size"]))
        print("  无字典比率 %.3f，带字典比率 %.3f，增益 %.3f → %s" % (
            report["baseline_ratio"], report["candidate_ratio"],
            report["gain"], report["reason"]))
        packed_dict = sum(len(store.encode(m)) for m in corpus)
        print("  带字典编码共 %d 字节，比无字典的 %d 字节省 %.1f%%" % (
            packed_dict, packed, (1 - packed_dict / packed) * 100))
        for index in (0, 5, 20, 77):
            got = store.decode(store.encode(corpus[index]))
            if got != corpus[index]:
                raise SystemExit("第 %d 条带字典解出来跟原文不一致" % index)
        print("  抽样带字典解回逐字节一致（帧头版本 v%d）" % store.active_version)
        again = store.rollout(corpus)
        print("  同语料再训一遍：增益 %.3f，%s" % (again["gain"], again["reason"]))


if __name__ == "__main__":
    main()
