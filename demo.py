"""msglz 演示。

第一段：造一小批总线短消息，逐条独立压缩，看看每条的编码尺寸。
第二段：预共享字典训练与版本管理——训练耗时、字典体积、实测比率、
不达标自动退回，以及多版本/老帧兼容。
"""

import random
import tempfile
import time

from msglz import DictStore, MessageCodec
from msglz import train_dictionary

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

    print()

    # ===== 第二段：预共享字典 =====
    with tempfile.TemporaryDirectory() as directory:
        store = DictStore(directory, max_versions=4, min_gain=0.05)
        train_corpus = make_corpus(400, seed=7)
        eval_corpus = make_corpus(200, seed=23)

        print("=== 预共享字典：首次 rollout ===")
        report = store.rollout(train_corpus)
        print("  训练 %d 条耗时 %.3f 秒，字典体积 %d 字节（上限 %d）"
              % (report["train_samples"], report["train_seconds"],
                 report["dict_size"], store.max_size))
        print("  评测 %d 条：无字典比率 %.3f（%d 字节）-> 带字典比率 %.3f"
              "（%d 字节）"
              % (report["eval_samples"], report["baseline_ratio"],
                 report["baseline_bytes"], report["candidate_ratio"],
                 report["candidate_bytes"]))
        print("  绝对收益 %.3f，门槛 %.2f：%s，现役版本=%s"
              % (report["gain"], report["min_gain"],
                 "上线" if report["promoted"] else "退回",
                 store.active_version))

        encoded = [store.encode(message) for message in eval_corpus]
        raw = sum(len(message) for message in eval_corpus)
        plain = sum(len(MessageCodec().encode(message))
                    for message in eval_corpus)
        packed = sum(len(frame) for frame in encoded)
        print("=== 换一拨没参与训练的流量（%d 条） ===" % len(eval_corpus))
        print("  原文 %d 字节；无字典 %d 字节（%.3f）；带字典 %d 字节（%.3f）"
              % (raw, plain, plain / raw, packed, packed / raw))
        print("  带字典比无字典省 %.1f%%，第一条 %d -> %d 字节"
              % ((1 - packed / plain) * 100,
                 len(eval_corpus[0]), len(encoded[0])))
        for index in (0, 5, 20, 77):
            if store.decode(encoded[index]) != eval_corpus[index]:
                raise SystemExit("第 %d 条解出来跟原文不一致" % index)
        print("  抽样解回逐字节一致；无字典老帧也照解：%s"
              % (store.decode(codec.encode(eval_corpus[1]))
                 == eval_corpus[1]))

        print("=== 不达标 rollout：拿随机噪声训一版 ===")
        rnd = random.Random(99)
        junk = [rnd.randbytes(120) for _ in range(200)]
        before = store.active_version
        rejected = store.rollout(junk)
        print("  候选版本 %d 字典体积 %d，收益 %.4f"
              % (rejected["version"], rejected["dict_size"],
                 rejected["gain"]))
        print("  %s（现役仍是版本 %s）：%s"
              % ("上线" if rejected["promoted"] else "原样退回",
                 store.active_version, rejected["reason"]))
        assert not rejected["promoted"] and before == store.active_version

        print("=== 一万条训练的耗时口径 ===")
        big = make_corpus(10000, seed=13)
        started = time.perf_counter()
        dictionary = train_dictionary(big, store.max_size)
        print("  10000 条训练 %.3f 秒，字典 %d 字节"
              % (time.perf_counter() - started, len(dictionary)))


if __name__ == "__main__":
    main()
