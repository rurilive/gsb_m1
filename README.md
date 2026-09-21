# logpipe

A small local pipeline for nested structured log records. Records are plain
dictionaries, the pipeline serializes each one to a single JSON line and
appends it to a sink.

## Layout

```
logpipe/
  paths.py      path parsing, lookup, mutation, leaf walking
  redact.py     rule compilation, masks, redact() and explain()
  records.py    record validation, deep clone, JSON encode/decode
  sink.py       MemorySink and JsonlFileSink
  pipeline.py   LogPipeline, the emit entry point
tests/          regression tests for the behaviour above
demo.py         end to end demo
```

## Redaction

Rules are plain dictionaries handed to a `Redactor`; attach it to a
pipeline with `set_redactor` and every subsequent `emit` writes the
redacted record while the caller's dict is never touched:

```python
redactor = Redactor([
    {"path": "user.phone", "mask": "phone"},
    {"path": "payments[?].card", "mask": "card"},
])
pipeline.set_redactor(redactor)
pipeline.emit(record)          # redacted line reaches the sink
```

A rule path uses the literal path syntax plus `[?]`, which matches every
in-range index of a list (`payments[?].card`, `grid[?][?]`); there is no
dict-key wildcard. Masks keep length and type stable:

- `phone` keeps the first three and last four characters;
- `card` keeps the last four characters;
- any other mask name stars the whole value.

Stars replace everything else one-for-one; when the value is too short
for the kept parts, stars win entirely. Non-string scalars that match a
rule are converted to text first (so the result is a string); dicts and
lists are never masked.

Precedence is fixed: the rule with the fewest `[?]` wildcards along the
whole path wins; between equally specific rules the one loaded later
wins. `Redactor.load_rules` compiles all rules into one path trie that
`redact` and `explain` reuse (the index is never rebuilt per record), and
calling it again atomically swaps in the new rule set, discarding the
old one.

`redact` returns a new redacted record; `explain(record[, path])`
returns, for every leaf, which rule and mask applied or why nothing did,
plus a per-rule diagnosis that pins missing keys, wrong container
types, concrete indices out of range, wildcards over non-lists and
wildcards over empty arrays.

### Bypass sink

Original records do not land anywhere by default. A rule may opt in with
`"bypass": true`; only records it actually matches are then also written
unredacted to the sink registered with `set_bypass_sink`:

```python
pipeline.set_bypass_sink(audit_sink)
redactor.load_rules([
    {"path": "payments[?].card", "mask": "card", "bypass": True},
])
```

### Robustness

Redaction is iterative with an explicit stack, so records nested tens of
thousands of levels deep and records containing cycles or shared
sub-objects neither crash nor leak unredacted data (cycles are preserved
inside the redacted copy). Wildcard indices past the end of a list and
empty arrays simply match zero items; the semantics are covered in
`tests/test_redact.py`, together with randomized structure/rule
differential tests against a naive reference implementation.

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
