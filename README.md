# logpipe

A small local pipeline for nested structured log records. Records are plain
dictionaries, the pipeline serializes each one to a single JSON line and
appends it to a sink.

## Layout

```
logpipe/
  paths.py      path parsing, lookup, mutation, leaf walking
  records.py    record validation, deep clone, JSON encode/decode
  sink.py       MemorySink and JsonlFileSink
  pipeline.py   LogPipeline, the emit entry point
tests/          regression tests for the behaviour above
demo.py         end to end demo
```

## Paths

A path is a dot separated chain of keys, each key may carry bracketed
non-negative integer indices:

```
user.phone
payments[0].card
grid[1][2]
```

Keys and indices are distinct namespaces: `rows.0` reads the key `"0"` of a
dict, `list[0]` reads the first item of a list. Anything other than an ascii
non-negative integer inside brackets raises `PathError`.

## Usage

```python
from logpipe import JsonlFileSink, LogPipeline, get_path

with JsonlFileSink("app.jsonl") as sink:
    pipeline = LogPipeline(sink)
    pipeline.emit({"user": {"phone": "13812345678"}})

get_path(record, "payments[0].card")        # raises PathError when absent
get_path(record, "user.email", default="-") # or fall back to a default
```

`LogPipeline` never mutates the record it is given and rejects non-dict
records with `TypeError` before anything reaches the sink. Lines are
serialized with sorted keys, so identical content always yields an
identical line.

## Running

```
python3 demo.py
python3 -m unittest discover -s tests
```
