"""巡检工具包演示。

第一段：跑一遍 扫描 -> 核查 -> 处置 流水线，日志走兼容模式，
与历史裸 print 逐行一致。
第二段：结构化日志层演示——级别过滤、上下文嵌套、文件轮转。
"""

import os
import tempfile

from loglite.checker import check
from loglite.logging import (
    DEBUG,
    RotatingFileSink,
    StreamSink,
    configure,
    get_logger,
    render_plain,
    reset_defaults,
    set_context,
)
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

    demo_structured()


def demo_structured():
    """第二段：结构化日志能力演示。

    用 stdout（带装饰的结构化渲染）+ 按大小轮转的文件 sink 同时落盘。
    """
    tmpdir = tempfile.mkdtemp(prefix="loglite-demo-")
    path = os.path.join(tmpdir, "pipeline.log")
    file_sink = RotatingFileSink(
        path, max_bytes=400, backups=2, renderer=render_plain
    )
    configure(
        level=DEBUG,
        sink=[StreamSink(renderer=render_plain), file_sink],
    )
    log = get_logger("demo")

    print("\n\n=== 结构化日志：级别 / 上下文嵌套 / 轮转 ===")
    log.debug("DEBUG 也会进来：当前全局级别是 DEBUG")
    log.info("这条没有上下文")
    with set_context(batch="nightly"):
        log.info("外层上下文：按批次分段")
        with set_context(stage="scan"):
            log.debug("内层上下文：批次保留，多了阶段")
        log.info("弹掉一层，回到外层批次上下文")
    log.info("上下文全部清空")

    for idx in range(24):
        log.debug(f"第 {idx + 1:02d} 条压日志，超过 400 字节就轮转")
    file_sink.close()
    reset_defaults()

    print("\n轮转产物（当前文件 + 旧文件后移，最多 2 个备份）：")
    for name in sorted(os.listdir(tmpdir)):
        size = os.path.getsize(os.path.join(tmpdir, name))
        print(f"  {name}: {size} bytes")
    print(f"\n目录: {tmpdir}")


if __name__ == "__main__":
    main()
