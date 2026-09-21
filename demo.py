"""End to end demo of the log pipeline.

Run with: python3 demo.py
"""

import os
import tempfile

from logpipe import (
    JsonlFileSink,
    LogPipeline,
    MemorySink,
    Redactor,
    get_path,
    walk_leaves,
)


def sample_records():
    return [
        {
            "ts": "2026-09-21T09:00:00Z",
            "service": "checkout",
            "level": "info",
            "user": {"id": 7, "phone": "13812345678", "city": "北京"},
        },
        {
            "ts": "2026-09-21T09:00:03Z",
            "service": "checkout",
            "level": "warn",
            "payments": [
                {"card": "6222020200112233", "amount": 12.5, "currency": "CNY"},
                {"card": "6222020200114455", "amount": 3, "currency": "CNY"},
            ],
            "tags": [],
        },
    ]


def main():
    with tempfile.TemporaryDirectory(prefix="logpipe-demo-") as tmp:
        path = os.path.join(tmp, "app.jsonl")
        with JsonlFileSink(path) as sink:
            pipeline = LogPipeline(sink)
            written = pipeline.emit_many(sample_records())

        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()

        print("sink:", type(sink).__name__)
        print("written:", written, "lines on disk:", len(lines))
        print()
        for line in lines:
            print(line)

        print()
        record = sample_records()[1]
        print("leaf paths of the last record:")
        for leaf_path, value in walk_leaves(record):
            print("  %-24s %r" % (leaf_path, value))

        print()
        print("point lookups:")
        print("  payments[1].card ->", get_path(record, "payments[1].card"))
        print("  level            ->", get_path(record, "level"))
        print("  user.email       ->", get_path(record, "user.email", default="<absent>"))

        print()
        print("pipeline stats:", pipeline.stats())

        # ---- extension demo slot ----
        print("compliance redaction:")
        redactor = Redactor([
            {"path": "user.phone", "mask": "phone"},
            # [?] masks every in-range payment index; an explicit index
            # would be more specific and win over the wildcard.
            {"path": "payments[?].card", "mask": "card", "bypass": True},
        ])
        redacted_path = os.path.join(tmp, "redacted.jsonl")
        bypass_sink = MemorySink()
        with JsonlFileSink(redacted_path) as redacted_sink:
            secure = LogPipeline(redacted_sink)
            secure.set_redactor(redactor)
            secure.set_bypass_sink(bypass_sink)
            for item in sample_records():
                line = secure.emit(item)
                print("  ", line)

            # Rules hot reload: the old rule set is fully discarded.
            redactor.load_rules([{"path": "user.phone", "mask": "all"}])
            print()
            print("  after reload:", secure.emit(sample_records()[0]))

        print()
        print("  originals bypassed to the audit sink:", len(bypass_sink.lines))
        for line in bypass_sink.lines:
            print("  ", line)

        print()
        print("  explain the payments record:")
        explanation = redactor.explain(sample_records()[1])
        for leaf in explanation["leaves"]:
            if leaf["redacted"]:
                print(
                    "    %-22s masked by %s via %s"
                    % (leaf["path"], leaf["mask"], leaf["rule"])
                )
        for rule in explanation["rules"]:
            print(
                "    rule %-22s %s (leaves=%d, containers=%d)"
                % (
                    rule["path"],
                    rule["status"],
                    rule["matched_leaves"],
                    rule["matched_containers"],
                )
            )


if __name__ == "__main__":
    main()
