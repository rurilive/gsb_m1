"""auditchain 演示：追加读回、重开续写、防篡改链、断尾、老日志补链、性能。"""

import json
import os
import tempfile
import time

from auditchain import AuditLog
from auditchain.codec import record_digest
from auditchain.store import RecordStore


def tamper(path, line_index, **changes):
    """手改磁盘上某一条的内容，故意不重算摘要，模拟被人动过手脚。"""
    with open(path, "rb") as handle:
        lines = handle.readlines()
    record = json.loads(lines[line_index])
    record.update(changes)
    lines[line_index] = json.dumps(
        record, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii") + b"\n"
    with open(path, "wb") as handle:
        handle.writelines(lines)


def demo_basic(tmpdir):
    print("=== 追加与读回 ===")
    path = os.path.join(tmpdir, "audit.log")
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


def demo_tamper(tmpdir):
    print("=== 手改中间一条处罚记录 ===")
    path = os.path.join(tmpdir, "tamper.log")
    log = AuditLog(path, checkpoint_every=5)
    for index in range(1, 13):
        log.append("punish", actor="wang", detail="扣发当月奖金 %d" % index, ts=index)
    tamper(path, 10, detail="警告一次")  # 第 11 条被洗白，在第 10 条检查点之后
    reopened = AuditLog(path, checkpoint_every=5)
    quick = reopened.verify()
    deep = reopened.verify(deep=True)
    print("  巡检（从最近检查点第10条起步）: ok=%s first_bad=第%s条 checked=%d"
          % (quick["ok"], quick["first_bad"], quick["checked"]))
    print(
        "  出事整链重核 deep=True: ok=%s first_bad=第%s条 last_good=第%d条 checked=%d"
        % (deep["ok"], deep["first_bad"], deep["last_good"], deep["checked"])
    )


def demo_torn_tail(tmpdir):
    print("=== 尾部写了一半被杀 ===")
    path = os.path.join(tmpdir, "torn.log")
    log = AuditLog(path, checkpoint_every=0)
    for index in range(1, 4):
        log.append("login", ts=index)
    with open(path, "ab") as handle:
        handle.write(b'{"seq":4,"act')
    reopened = AuditLog(path, checkpoint_every=0)
    result = reopened.verify()
    print("  半行尾巴不认作坏: ok=%s last_good=第%d条" % (result["ok"], result["last_good"]))
    reopened.append("login", ts=4)
    print("  自愈后续写第 4 条，整链重核: %s" % reopened.verify(deep=True)["ok"])


def demo_legacy(tmpdir):
    print("=== 老版本日志（没有链字段）就地补链 ===")
    path = os.path.join(tmpdir, "legacy.log")
    store = RecordStore(path)
    for index in range(1, 4):  # 老版本：只有内容摘要 digest
        record = {
            "seq": index,
            "ts": float(index),
            "action": "old%d" % index,
            "actor": "",
            "detail": "",
        }
        record["digest"] = record_digest(record)
        store.append(record)
    log = AuditLog(path, checkpoint_every=0)
    new_record = log.append("login", ts=4)
    print("  老日志照常打开、补齐链、序号续到 %d" % new_record["seq"])
    deep = log.verify(deep=True)
    print("  整链重核: ok=%s checked=%d" % (deep["ok"], deep["checked"]))


def demo_scale(tmpdir):
    print("=== 十万条：追加、巡检、整链重核计时 ===")
    path = os.path.join(tmpdir, "big.log")
    log = AuditLog(path, checkpoint_every=1000)
    start = time.perf_counter()
    for index in range(1, 100001):
        log.append("punish", detail="记录%d" % index, ts=index)
    append_seconds = time.perf_counter() - start
    start = time.perf_counter()
    quick = log.verify()
    quick_seconds = time.perf_counter() - start
    start = time.perf_counter()
    deep = log.verify(deep=True)
    deep_seconds = time.perf_counter() - start
    print("  追加 100000 条: %.2fs" % append_seconds)
    print("  巡检实际核对 %d 条: %.3fs" % (quick["checked"], quick_seconds))
    print("  整链重核 %d 条: %.3fs" % (deep["checked"], deep_seconds))


def main():
    tmpdir = tempfile.mkdtemp(prefix="auditchain-demo-")
    demo_basic(tmpdir)
    demo_tamper(tmpdir)
    demo_torn_tail(tmpdir)
    demo_legacy(tmpdir)
    demo_scale(tmpdir)
    print("=== 日志文件目录: %s ===" % tmpdir)


if __name__ == "__main__":
    main()
