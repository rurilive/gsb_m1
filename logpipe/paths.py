"""Reading and writing nested log records by path.

A path is a dot separated chain of keys. Each key may carry one or more
bracketed non-negative integer indices::

    user.phone
    payments[0].card
    grid[1][2]

Keys and indices are not interchangeable. In the record
``{"rows": {"0": "x"}, "list": ["y"]}`` the path ``rows.0`` reads a dict
key while ``list[0]`` reads a list item; the two never resolve to each
other.

Every bracket must hold a non-negative integer, written with ascii
digits. Anything else, including empty brackets and negative or
non-numeric indices, is rejected with :class:`PathError`.
"""

_MISSING = object()


class PathError(ValueError):
    """A path is malformed or does not resolve against a record."""


def parse_path(path):
    """Turn a path string into ("key", name) / ("index", n) tuples."""
    if not isinstance(path, str) or not path:
        raise PathError("path must be a non-empty string")
    segments = []
    for part in path.split("."):
        if not part:
            raise PathError("empty segment in path %r" % (path,))
        name, indices = _split_part(part, path)
        if name:
            segments.append(("key", name))
        for index in indices:
            segments.append(("index", index))
    if not segments:
        raise PathError("empty path %r" % (path,))
    return segments


def _split_part(part, path):
    if "[" not in part:
        if "]" in part:
            raise PathError("stray bracket in path %r" % (path,))
        return part, []
    name, rest = part.split("[", 1)
    rest = "[" + rest
    indices = []
    while rest:
        if not rest.startswith("["):
            raise PathError("malformed segment %r in path %r" % (part, path))
        end = rest.find("]")
        if end < 0:
            raise PathError("unterminated bracket in path %r" % (path,))
        token = rest[1:end]
        if not token.isascii() or not token.isdigit():
            raise PathError(
                "index %r in path %r is not a non-negative integer" % (token, path)
            )
        indices.append(int(token))
        rest = rest[end + 1:]
    return name, indices


def format_path(segments):
    """Render ("key", name) / ("index", n) segments back into a path string."""
    parts = []
    for kind, value in segments:
        if kind == "key":
            if parts:
                parts.append(".")
            parts.append(str(value))
        elif kind == "index":
            parts.append("[%d]" % value)
        else:
            raise PathError("unknown segment kind %r" % (kind,))
    return "".join(parts)


def get_path(record, path, default=_MISSING):
    """Resolve a path against a record.

    Raises :class:`PathError` when a key is missing, a value has the wrong
    container type or an index is out of range. Pass ``default`` to get a
    fallback instead of the exception.
    """
    try:
        return _resolve(record, parse_path(path))
    except PathError:
        if default is not _MISSING:
            return default
        raise


def set_path(record, path, value):
    """Replace an existing value addressed by a path.

    The parent container and the target slot must already exist; this
    helper never creates intermediate keys or extends lists.
    """
    segments = parse_path(path)
    if len(segments) > 1:
        parent = _resolve(record, segments[:-1])
    else:
        parent = record
    kind, key = segments[-1]
    if kind == "key":
        if not isinstance(parent, dict):
            raise PathError("cannot set key %r on %s" % (key, _type_name(parent)))
        if key not in parent:
            raise PathError("missing key %r" % (key,))
        parent[key] = value
    else:
        if not isinstance(parent, list):
            raise PathError("cannot set index [%d] on %s" % (key, _type_name(parent)))
        if not 0 <= key < len(parent):
            raise PathError(
                "index %d out of range on list of length %d" % (key, len(parent))
            )
        parent[key] = value
    return value


def walk_leaves(record):
    """Yield ``(path, value)`` for every leaf of a record.

    Dictionaries are walked in insertion order, lists in index order.
    Empty dicts and empty lists contribute nothing.
    """
    yield from _walk_leaves(record, ())


def _walk_leaves(record, segments):
    if isinstance(record, dict):
        for key in record:
            yield from _walk_leaves(record[key], segments + (("key", key),))
    elif isinstance(record, list):
        for index, item in enumerate(record):
            yield from _walk_leaves(item, segments + (("index", index),))
    else:
        yield format_path(segments), record


def _resolve(record, segments):
    current = record
    for position, (kind, value) in enumerate(segments):
        if kind == "key":
            if not isinstance(current, dict):
                raise PathError(
                    "cannot look up key %r on %s" % (value, _type_name(current))
                )
            if value not in current:
                raise PathError(
                    "missing key %r under %r"
                    % (value, format_path(segments[:position]))
                )
            current = current[value]
        else:
            if not isinstance(current, list):
                raise PathError(
                    "cannot index %s with [%d]" % (_type_name(current), value)
                )
            if not 0 <= value < len(current):
                raise PathError(
                    "index %d out of range under %r, list has %d items"
                    % (value, format_path(segments[:position]), len(current))
                )
            current = current[value]
    return current


def _type_name(value):
    return type(value).__name__
