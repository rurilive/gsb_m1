"""Record cloning and JSON encoding helpers."""

import copy
import json


def check_record(record):
    """Reject anything that is not a plain dict record."""
    if not isinstance(record, dict):
        raise TypeError("record must be a dict, got %s" % type(record).__name__)
    return record


def clone(record):
    """Return a deep copy of a record.

    Cyclic references inside the record are copied as such, so the copy
    keeps pointing at itself instead of recursing forever.
    """
    return copy.deepcopy(record)


def is_leaf(value):
    """A leaf is any value that is neither a dict nor a list."""
    return not isinstance(value, (dict, list))


def dumps(record):
    """Serialize a record into one deterministic JSON line.

    Keys are sorted and non-ascii text is kept readable, so two records
    with the same content always produce the same line.
    """
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def loads(line):
    """Parse a single JSON line back into a record."""
    return json.loads(line)
