"""End to end demo of the log pipeline.

Run with: python3 demo.py
"""

import os
import tempfile

from logpipe import JsonlFileSink, LogPipeline, get_path, walk_leaves


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
        # Hook new pipeline capabilities in here once they land.


if __name__ == "__main__":
    main()
