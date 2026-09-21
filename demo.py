"""auditchain 现状演示。

第一段：写几条审计记录，读回来看内容和摘要。
第二段：关掉重开，接着往下写，看序号续上、摘要重算一致。
第三段：防篡改链：十万条追加加校验计时、手改记录被揪出来、
截尾巴认出最后一致点、老版本日志就地补链。
"""

import json
import os
import tempfile
import time

from auditchain import AuditLog
from auditchain.codec import record_digest


def main():
    tmpdir = tempfile.mkdtemp(prefix="auditchain-demo-")
    path = os.path.join(tmpdir, "audit.log")

    print("=== 追加与读回 ===")
    log = AuditLog(path)
    log.append("login", actor="zhang", detail="10.0.0.7", ts=1700000000)
    log.append("export", actor="li", detail="客户名单", ts=1700000001)
    log.append("punish", actor="wang", detail="扣发当月奖金", ts=1700000002)
    for record in log.read_all():
        print(
            "  seq=%d %s by %s digest=%s"
            % (record["seq"], record["action"], record["actor"], record["digest"][:12])
        )
    print("  count = %d" % log.count())

    print("=== 重开再写 ===")
    log = AuditLog(path)
    log.append("login", actor="li", ts=1700000003)
    newest = log.last()
    print("  重开后 count = %d，最新一条 seq = %d" % (log.count(), newest["seq"]))
    print("  摘要重算一致: %s" % (record_digest(newest) == newest["digest"]))

    print("=== 防篡改链 ===")
    bulk_path = os.path.join(tmpdir, "bulk.log")
    bulk = AuditLog(bulk_path)
    started = time.monotonic()
    for i in range(100000):
        bulk.append("bulk", actor="demo", ts=1700000100 + i)
    append_seconds = time.monotonic() - started
    started = time.monotonic()
    result = bulk.verify()
    verify_seconds = time.monotonic() - started
    print(
        "  十万条追加 %.2fs，默认校验 %.2fs（checked=%d，从检查点起步）"
        % (append_seconds, verify_seconds, result["checked"])
    )
    started = time.monotonic()
    deep = bulk.verify(deep=True)
    print("  整链重核 %.2fs（checked=%d）ok=%s" % (time.monotonic() - started, deep["checked"], deep["ok"]))

    print("=== 手改一条处罚记录 ===")
    with open(bulk_path, "rb") as handle:
        lines = handle.read().split(b"\n")
    record = json.loads(lines[49999].decode("ascii"))
    record["detail"] = "改成不处罚"
    lines[49999] = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    with open(bulk_path, "wb") as handle:
        handle.write(b"\n".join(lines))
    result = AuditLog(bulk_path).verify(deep=True)
    print(
        "  deep 校验 ok=%s，第一条坏记录 seq=%s，最后一致点 seq=%s"
        % (result["ok"], result["first_bad"], result["last_good"])
    )

    print("=== 尾巴被截 ===")
    tail_path = os.path.join(tmpdir, "tail.log")
    tail = AuditLog(tail_path, checkpoint_every=1000)
    for i in range(5000):
        tail.append("tail", actor="demo", ts=1700000300 + i)
    with open(tail_path, "ab") as handle:
        handle.write(b'{"seq":5001,"act')
    result = AuditLog(tail_path, checkpoint_every=1000).verify()
    print("  多了半条没写完的：ok=%s，last_good=%s" % (result["ok"], result["last_good"]))
    with open(tail_path, "rb") as handle:
        lines = handle.read().split(b"\n")[:4200]
    with open(tail_path, "wb") as handle:
        handle.write(b"\n".join(lines) + b"\n")
    result = AuditLog(tail_path, checkpoint_every=1000).verify()
    print(
        "  尾巴被截掉几百条：ok=%s，缺口从 seq=%s 开始，last_good=%s"
        % (result["ok"], result["first_bad"], result["last_good"])
    )

    print("=== 老版本日志就地补链 ===")
    legacy_path = os.path.join(tmpdir, "legacy.log")
    with open(legacy_path, "wb") as handle:
        for seq in range(1, 4):
            old = {"seq": seq, "ts": float(seq), "action": "legacy"}
            old["digest"] = record_digest(old)
            handle.write(
                json.dumps(old, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
            )
    legacy = AuditLog(legacy_path)
    legacy.append("new", actor="demo", ts=1700000200)
    result = legacy.verify(deep=True)
    print(
        "  老日志打开没报错，补链后续写 seq=%d，deep 校验 ok=%s"
        % (legacy.count(), result["ok"])
    )

    print("=== 日志文件: %s ===" % path)


if __name__ == "__main__":
    main()
