"""auditchain 现状演示。

第一段：写几条审计记录，读回来看内容和摘要。
第二段：关掉重开，接着往下写，看序号续上、摘要重算一致。
第三段：防篡改链的演示位子（见文末注释）。
"""

import os
import tempfile

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

    # TODO(防篡改链): 链和检查点做完之后，在这里加一段演示：
    # 攒到十万条看一次追加和一次校验各花多少时间；
    # 手动改掉中间某条再校验，看报出来的第一条坏记录是第几条；
    # 再把尾巴截掉半条，看最后一个一致点落在哪；
    # 顺手拿一份老版本写的日志文件，看能不能继续用。

    print("=== 日志文件: %s ===" % path)


if __name__ == "__main__":
    main()
