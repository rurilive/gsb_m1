"""巡检工具包演示。

第一段：跑一遍 扫描 -> 核查 -> 处置 流水线（兼容模式，与旧 print 一致）。
第二段：结构化日志层演示——级别过滤、上下文嵌套、文件轮转采集。
"""

import os
import tempfile

from loglite.checker import check
from loglite import logging as loglite_logging
from loglite.manifest import dump, parse
from loglite.planner import plan, summary
from loglite.scanner import scan

MANIFEST = """\
# name size mtime
site.conf      2048      1758000000
notes.txt      512       1758000100
cache.tmp      65536     1758000200
site.conf      2048      1758000300
huge.blob      9437184   1758000400
editor.swp     4096      1758000500
"""


def main():
    entries = parse(MANIFEST)
    print(f"=== 巡检流水线（{len(entries)} 个条目） ===\n")

    flagged = scan(entries)
    print()
    problems = check(entries)
    print()
    actions = plan(problems)

    print("\n=== 结果 ===")
    print(f"  可疑条目: {flagged}")
    print(f"  问题清单: {problems}")
    print(f"  处置动作: {actions}")
    print(f"  动作汇总: {summary(actions)}")
    kept = [e for e in entries if e[0] not in flagged]
    print(f"\n清理后的清单预览:\n{dump(kept)}", end="")

    demo_structured_logging()


def demo_structured_logging():
    print("\n\n=== 结构化日志演示 ===")

    capture = loglite_logging.CaptureSink(render=loglite_logging.JSON)
    loglite_logging.configure(level="DEBUG", sinks=[capture])
    log = loglite_logging.get_logger("demo")

    print("-- 级别过滤（全局 WARNING，DEBUG/INFO 不进 sink）--")
    loglite_logging.configure(level="WARNING", sinks=[capture])
    log.debug("调试细节：被过滤")
    log.info("常规信息：被过滤")
    log.warning("警告：保留")
    log.error("错误：保留")
    loglite_logging.configure(level="DEBUG")

    print("-- 上下文嵌套：压两层弹一层，回到上一层 --")
    outer = loglite_logging.set_context(job="nightly", host="node-1")
    log.info("外层上下文")
    inner = loglite_logging.set_context(stage="checker", entry="site.conf")
    log.info("内层上下文")
    loglite_logging.clear_context(inner)
    log.info("弹回外层")
    loglite_logging.clear_context(outer)

    for line in capture.lines:
        print("  " + line)

    print("-- 文件 sink + 按大小轮转 --")
    tmpdir = tempfile.mkdtemp(prefix="loglite-demo-")
    path = os.path.join(tmpdir, "inspect.log")
    file_sink = loglite_logging.FileSink(path, max_bytes=768, backups=3)
    loglite_logging.configure(level="DEBUG", sinks=[file_sink])
    with loglite_logging.set_context(run="demo"):
        for index in range(16):
            log.debug(f"轮转演示第 {index:02d} 条")
    file_sink.close()

    names = sorted(
        name for name in os.listdir(tmpdir) if name.startswith("inspect.log")
    )
    total = 0
    for name in names:
        full = os.path.join(tmpdir, name)
        count = sum(1 for _ in open(full, encoding="utf-8"))
        total += count
        print(f"  {name}: {count} 行, {os.path.getsize(full)} bytes")
    print(f"  共 {total} 条记录，跨 {len(names)} 个文件，一条不丢")

    loglite_logging.reset()


if __name__ == "__main__":
    main()
