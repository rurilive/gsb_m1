"""auditchain 演示：追加读回、防篡改链、检查点、截尾与老日志补链。"""

import json
import os
import tempfile
import time

from auditchain import AuditLog
from auditchain.codec import PREV_FIELD, encode_line, record_digest


def tamper_one_line(path, seq, **changes):
    """模拟有人手改进文件：只改第 seq 条的字段，摘要和后面的链都不动。"""
    with open(path, "rb") as handle:
        lines = handle.read().splitlines(keepends=True)
    record = json.loads(lines[seq - 1])
    stale_digest = record["digest"]
    record.update(changes)
    record["digest"] = stale_digest
    lines[seq - 1] = encode_line(record)
    with open(path, "wb") as handle:
        handle.writelines(lines)


def main():
    tmpdir = tempfile.mkdtemp(prefix="auditchain-demo-")
    path = os.path.join(tmpdir, "audit.log")

    print("=== 追加与读回 ===")
    log = AuditLog(path, checkpoint_every=5)
    log.append("login", actor="zhang", detail="10.0.0.7", ts=1700000000)
    log.append("export", actor="li", detail="客户名单", ts=1700000001)
    log.append("punish", actor="wang", detail="扣发当月奖金", ts=1700000002)
    for record in log.read_all():
        print(
            "  seq=%d %s by %s prev=%s digest=%s"
            % (
                record["seq"],
                record["action"],
                record["actor"],
                record[PREV_FIELD][:8],
                record["digest"][:8],
            )
        )
    print("  count = %d" % log.count())

    print("=== 重开再写 ===")
    log = AuditLog(path, checkpoint_every=5)
    newest = log.append("login", actor="li", ts=1700000003)
    print("  重开后 count = %d，最新一条 seq = %d" % (log.count(), newest["seq"]))
    print("  摘要重算一致: %s" % (record_digest(newest) == newest["digest"]))

    print("=== 防篡改：手改第 2 条处罚记录 ===")
    for seq in range(log.count() + 1, 13):
        log.append("audit", actor="sys", detail="例行记录", ts=1700000000.0 + seq)
    tamper_one_line(path, 2, detail="扣发当月奖金（已撤销）")
    reopened = AuditLog(path, checkpoint_every=5)
    print("  巡检 shallow : %s" % reopened.verify())
    print("  整链 deep    : %s" % reopened.verify(deep=True))

    print("=== 截尾：认出最后一个一致点 ===")
    torn_path = os.path.join(tmpdir, "torn.log")
    torn = AuditLog(torn_path, checkpoint_every=5)
    for seq in range(1, 13):
        torn.append("audit", ts=1700000000.0 + seq)
    with open(torn_path, "ab") as handle:
        handle.write(b'{"seq":13,"act')
    recovered = AuditLog(torn_path, checkpoint_every=5)
    print("  半行尾巴打开: count=%d verify=%s" % (recovered.count(), recovered.verify()))
    print("  整段截到第 8 条:")
    with open(torn_path, "rb") as handle:
        lines = handle.readlines()
    os.truncate(torn_path, sum(len(line) for line in lines[:8]))
    cut = AuditLog(torn_path, checkpoint_every=5)
    print("  deep         : %s" % cut.verify(deep=True))

    print("=== 老日志就地补链 ===")
    old_path = os.path.join(tmpdir, "legacy.log")
    with open(old_path, "wb") as handle:
        for seq in range(1, 4):
            record = {
                "seq": seq,
                "ts": 1700000000.0 + seq,
                "action": "punish",
                "actor": "old",
                "detail": "上一版写的记录",
            }
            record["digest"] = record_digest(record)
            handle.write(encode_line(record))
    legacy = AuditLog(old_path, checkpoint_every=5)
    print("  打开老日志不报错: count=%d" % legacy.count())
    legacy.append("punish", actor="new", detail="补链后新写", ts=1700000010.0)
    print("  续写后整链校验  : %s" % legacy.verify(deep=True))

    print("=== 十万条性能 ===")
    big_path = os.path.join(tmpdir, "big.log")
    big = AuditLog(big_path)
    start = time.perf_counter()
    for seq in range(1, 100001):
        big.append("login", actor="u%d" % seq, detail="x", ts=float(seq))
    appended = time.perf_counter()
    shallow = big.verify()
    checked_shallow = time.perf_counter()
    deep = big.verify(deep=True)
    checked_deep = time.perf_counter()
    print(
        "  追加 %.1fs，巡检 %.2fs（重算 %d 条），整链 %.2fs（%d 条）"
        % (
            appended - start,
            checked_shallow - appended,
            shallow["checked"],
            checked_deep - checked_shallow,
            deep["checked"],
        )
    )

    print("=== 临时目录: %s ===" % tmpdir)


if __name__ == "__main__":
    main()
