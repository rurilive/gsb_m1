"""auditchain 现状演示。

第一段：写几条审计记录，读回来看内容和摘要。
第二段：关掉重开，接着往下写，看序号续上、摘要重算一致。
第三段：防篡改链，十万条计时、篡改定位、截尾容忍、老日志补链。
"""

import json
import os
import tempfile
import time

from auditchain import AuditLog
from auditchain.codec import encode_line, record_digest


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
    started = time.monotonic()
    for i in range(100000):
        log.append("job", actor="bulk", detail="n%d" % i, ts=1700000100 + i)
    appended = time.monotonic()
    deep = log.verify(deep=True)
    verified = time.monotonic()
    print("  追加 100000 条耗时 %.2fs" % (appended - started))
    print(
        "  整链校验耗时 %.2fs: ok=%s checked=%d"
        % (verified - appended, deep["ok"], deep["checked"])
    )
    shallow = log.verify()
    print("  巡检校验: ok=%s checked=%d（从最近检查点起步）" % (shallow["ok"], shallow["checked"]))

    print("=== 手动篡改 ===")
    with open(path, "rb") as handle:
        lines = handle.read().splitlines()
    record = json.loads(lines[2].decode("ascii"))
    record["detail"] = "处罚记录被悄悄改了"
    lines[2] = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    with open(path, "wb") as handle:
        handle.write(b"\n".join(lines) + b"\n")
    result = log.verify(deep=True)
    print(
        "  改掉第 3 条后整链重核: ok=%s first_bad=%s last_good=%s"
        % (result["ok"], result["first_bad"], result["last_good"])
    )

    print("=== 截掉的尾巴 ===")
    tail_path = os.path.join(tmpdir, "tail.log")
    tail_log = AuditLog(tail_path)
    for i in range(5):
        tail_log.append("job", actor="t", detail="d%d" % i, ts=1700000200 + i)
    with open(tail_path, "ab") as handle:
        handle.write(b'{"seq":6,"act')  # 写了一半进程就没了
    result = tail_log.verify(deep=True)
    print(
        "  尾巴挂着半条: ok=%s last_good=%s（最后一个一致点）"
        % (result["ok"], result["last_good"])
    )

    print("=== 老日志补链 ===")
    legacy_path = os.path.join(tmpdir, "legacy.log")
    with open(legacy_path, "wb") as handle:
        for i in range(3):
            old = {
                "seq": i + 1,
                "ts": 1600000000.0 + i,
                "action": "legacy",
                "actor": "old",
                "detail": "上一版写的",
            }
            old["digest"] = record_digest(old)
            handle.write(encode_line(old))
    legacy = AuditLog(legacy_path)
    result = legacy.verify(deep=True)
    print(
        "  老日志打开后: count=%d verify ok=%s，续写 seq=%d"
        % (legacy.count(), result["ok"], legacy.append("new", ts=1700000300)["seq"])
    )

    print("=== 日志文件: %s ===" % path)


if __name__ == "__main__":
    main()
