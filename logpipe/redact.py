"""Rule based redaction for nested log records.

Rules are plain dictionaries::

    {"path": "user.phone", "mask": "phone"}
    {"path": "payments[?].card", "mask": "card", "bypass": True}

A path follows the syntax of :mod:`logpipe.paths`, but a bracketed index
may be the single token ``?`` which matches any in-range list index.
There is no wildcard for dict keys.

``phone`` keeps the first three and last four characters, ``card`` keeps
the last four; every other character (and the whole value for any other
mask name) is replaced by ``*``. Result length always equals the textual
value length; when a value is too short for the kept parts, stars win and
nothing is kept, so overlap never leaks characters. Matched non-string
scalars are converted to text first; containers are never masked.

The rule with the fewest ``?`` wildcards along the whole path wins; ties
are resolved by load order (later wins). Rules compile once per
:meth:`Redactor.load_rules` call into a path trie reused by ``redact``
and ``explain``; reloading atomically replaces every rule and index.
"""

from .paths import PathError, format_path, parse_path
from .records import check_record

WILDCARD = "?"


class RuleError(ValueError):
    """A redaction rule is malformed."""


def mask_phone(text):
    """Keep the first three and last four characters, star the middle."""
    return _mask_keep(text, 3, 4)


def mask_card(text):
    """Keep the last four characters, star everything before them."""
    return _mask_keep(text, 0, 4)


def mask_all(text):
    """Star every character."""
    return "*" * len(text)


def _mask_keep(text, head, tail):
    length = len(text)
    if length <= head + tail:
        return "*" * length
    return text[:head] + "*" * (length - head - tail) + text[length - tail:]


_MASKS = {"phone": mask_phone, "card": mask_card}


def apply_mask(name, text):
    """Apply a named mask to text; unknown names star everything."""
    if not isinstance(name, str) or not name:
        raise RuleError("mask must be a non-empty string, got %r" % (name,))
    return _MASKS.get(name, mask_all)(text)


def parse_pattern(path):
    """Parse a rule path into key/index/wildcard segments."""
    if not isinstance(path, str) or not path:
        raise PathError("rule path must be a non-empty string")
    segments = []
    for part in path.split("."):
        if not part:
            raise PathError("empty segment in rule path %r" % (path,))
        name, indices = _split_pattern_part(part, path)
        if name:
            segments.append(("key", name))
        segments.extend(indices)
    if not segments:
        raise PathError("empty rule path %r" % (path,))
    return segments


def _split_pattern_part(part, path):
    if "[" not in part:
        if "]" in part:
            raise PathError("stray bracket in rule path %r" % (path,))
        return part, []
    name, rest = part.split("[", 1)
    rest = "[" + rest
    indices = []
    while rest:
        if not rest.startswith("["):
            raise PathError("malformed segment %r in rule path %r" % (part, path))
        end = rest.find("]")
        if end < 0:
            raise PathError("unterminated bracket in rule path %r" % (path,))
        token = rest[1:end]
        if token == WILDCARD:
            indices.append(("wildcard", WILDCARD))
        elif token.isascii() and token.isdigit():
            indices.append(("index", int(token)))
        else:
            raise PathError(
                "index %r in rule path %r must be a non-negative integer or '?'"
                % (token, path)
            )
        rest = rest[end + 1:]
    return name, indices


def format_pattern(segments):
    """Render parsed rule segments back to a path string."""
    parts = []
    for kind, value in segments:
        if kind == "key":
            if parts:
                parts.append(".")
            parts.append(str(value))
        elif kind == "index":
            parts.append("[%d]" % value)
        elif kind == "wildcard":
            parts.append("[?]")
        else:
            raise PathError("unknown segment kind %r" % (kind,))
    return "".join(parts)


class _Node:
    __slots__ = ("edges", "payload")

    def __init__(self):
        self.edges = {}
        self.payload = None


def _new_trie(compiled):
    """Compile (segments, payload) pairs into a path trie.

    A duplicate concrete path replaces the earlier payload, so the later
    rule wins. The trie is built once and never mutated afterwards.
    """
    root = _Node()
    for segments, payload in compiled:
        node = root
        for segment in segments:
            edge = ("wildcard",) if segment[0] == "wildcard" else segment
            next_node = node.edges.get(edge)
            if next_node is None:
                next_node = _Node()
                node.edges[edge] = next_node
            node = next_node
        node.payload = payload
    return root


def _advance_all(nodes, edge):
    """All distinct trie nodes reachable from ``nodes`` over one edge.

    Concrete index edges follow both the literal edge and the wildcard
    edge; dict-key edges follow only the literal edge. Duplicate nodes
    (reachable through several prefixes) are collapsed.
    """
    result = []
    seen = set()
    is_index = edge[0] == "index"
    for node in nodes:
        nxt = node.edges.get(edge)
        if nxt is not None and id(nxt) not in seen:
            seen.add(id(nxt))
            result.append(nxt)
        if is_index:
            wildcard = node.edges.get(("wildcard",))
            if wildcard is not None and id(wildcard) not in seen:
                seen.add(id(wildcard))
                result.append(wildcard)
    return tuple(result)


def _outranks(payload, current):
    """True if ``payload`` wins over ``current`` at the same leaf."""
    if payload["wildcards"] != current["wildcards"]:
        return payload["wildcards"] < current["wildcards"]
    return payload["order"] > current["order"]


def _compile_rule(rule, order):
    if not isinstance(rule, dict):
        raise RuleError("each rule must be a dict, got %s" % type(rule).__name__)
    if "path" not in rule:
        raise RuleError("rule %r is missing a 'path'" % (rule,))
    if "mask" not in rule:
        raise RuleError("rule %r is missing a 'mask'" % (rule,))
    mask = rule["mask"]
    if not isinstance(mask, str) or not mask:
        raise RuleError("rule %r mask must be a non-empty string" % (rule,))
    segments = parse_pattern(rule["path"])
    payload = {
        "path": format_pattern(segments),
        "mask": mask,
        "bypass": bool(rule.get("bypass", False)),
        "order": order,
        "wildcards": sum(1 for kind, _ in segments if kind == "wildcard"),
        "segments": segments,
    }
    return segments, payload


def _items(obj):
    if isinstance(obj, dict):
        return list(obj.items())
    return list(enumerate(obj))


def _blank(obj):
    if isinstance(obj, dict):
        return {}
    return [None] * len(obj)


def _edge_to_segment(edge):
    if edge[0] == "wildcard":
        return ("wildcard", WILDCARD)
    return edge


def _to_text(value):
    """Return ``(text, coerced)`` for a leaf value."""
    if isinstance(value, str):
        return value, False
    if value is None:
        return "null", True
    if value is True:
        return "true", True
    if value is False:
        return "false", True
    return str(value), True


def _event_to_leaf(event):
    leaf = {"path": event["path"], "redacted": event["redacted"]}
    if event["redacted"]:
        leaf["mask"] = event["mask"]
        leaf["rule"] = event["rule_path"]
        leaf["bypass"] = event["bypass"]
        leaf["coerced"] = event["coerced"]
        leaf["length"] = event["length"]
    else:
        leaf["reason"] = event["reason"]
    return leaf


class Redactor:
    """Compile rules and redact records with a reusable path index."""

    def __init__(self, rules=None):
        self._root = _Node()
        self._payloads = []
        self._version = 0
        if rules is not None:
            self.load_rules(rules)

    @property
    def version(self):
        """Number of successful :meth:`load_rules` calls so far."""
        return self._version

    def load_rules(self, rules):
        """Compile rules and atomically replace the previous rule set.

        Returns ``self``. Rules loaded before are fully discarded; no
        compiled rule or index entry survives the reload. The index is
        built once here and is never rebuilt per record.
        """
        if isinstance(rules, (str, bytes)) or not hasattr(rules, "__iter__"):
            raise RuleError("rules must be an iterable of rule dicts")
        compiled = []
        payloads = []
        for position, rule in enumerate(rules):
            segments, payload = _compile_rule(rule, position)
            compiled.append((segments, payload))
            payloads.append(payload)
        self._root = _new_trie(compiled)
        self._payloads = payloads
        self._version += 1
        return self

    def redact(self, record):
        """Return a deep-copied, redacted record. The input is untouched."""
        check_record(record)
        redacted, _ = self._walk(record, want_events=False)
        return redacted

    def explain(self, record, path=None):
        """Explain why leaves were or were not redacted.

        Returns a dict with ``leaves`` (one deterministic entry per leaf
        actually present) and ``rules`` (one entry per loaded rule with
        its own resolution diagnosis, covering out-of-range indices,
        wildcard misses against empty arrays and wrong-container steps).
        Pass ``path`` for an extra ``leaf`` entry for one leaf.
        """
        check_record(record)
        redacted, (events, _wins) = self._walk(record, want_events=True)
        del redacted
        result = {
            "leaves": [_event_to_leaf(event) for event in events],
            "rules": self._explain_rules(record, events),
        }
        if path is not None:
            target = format_path(parse_path(path))
            for event in events:
                if event["path"] == target:
                    result["leaf"] = _event_to_leaf(event)
                    break
            else:
                raise PathError(
                    "path %r does not address a leaf of the record" % path
                )
        return result

    def _walk(self, record, want_events):
        """Iteratively clone ``record`` while applying matching rules.

        A memo keyed by ``id`` keeps shared sub-objects shared in the copy
        and closes cycles, so cyclic records neither loop forever nor
        leak unredacted data. The stack is explicit, so arbitrarily deep
        nesting cannot hit Python's recursion limit.

        Each container carries *all* trie nodes reachable by any rule
        prefix at that depth, so a concrete index that misses still keeps
        a sibling wildcard branch alive (``a[0]`` and ``a[?]`` coexist).
        Concrete leaf paths are only built when ``want_events`` is set.
        """
        root_node = self._root
        events = [] if want_events else None
        wins = {}
        root_copy = _blank(record)
        memo = {id(record): root_copy}
        # frame: [obj, copy, active_nodes, path_text, pending, index]
        stack = [[
            record, root_copy, (root_node,), "", _items(record), 0,
        ]]

        while stack:
            frame = stack[-1]
            obj, copy_obj, active_nodes, path_text = frame[0:4]
            pending, index = frame[4], frame[5]
            if index >= len(pending):
                stack.pop()
                continue
            frame[5] = index + 1
            key, child = pending[index]
            edge = ("key", key) if isinstance(obj, dict) else ("index", key)
            child_nodes = _advance_all(active_nodes, edge)

            if isinstance(child, (dict, list)):
                cached = memo.get(id(child))
                if cached is not None:
                    copy_obj[key] = cached
                    continue
                child_copy = _blank(child)
                memo[id(child)] = child_copy
                copy_obj[key] = child_copy
                child_path = _append_path(path_text, edge) if want_events else ""
                stack.append([
                    child, child_copy, child_nodes, child_path,
                    _items(child), 0,
                ])
                continue

            best = None
            for node in child_nodes:
                payload = node.payload
                if payload is not None and (
                    best is None or _outranks(payload, best)
                ):
                    best = payload

            if best is None:
                copy_obj[key] = child
                if want_events:
                    events.append({
                        "path": _append_path(path_text, edge),
                        "redacted": False,
                        "reason": "no matching rule",
                    })
            else:
                text, coerced = _to_text(child)
                copy_obj[key] = apply_mask(best["mask"], text)
                wins[best["order"]] = wins.get(best["order"], 0) + 1
                if want_events:
                    events.append({
                        "path": _append_path(path_text, edge),
                        "redacted": True,
                        "mask": best["mask"],
                        "rule_path": best["path"],
                        "bypass": best["bypass"],
                        "coerced": coerced,
                        "length": len(text),
                    })

        return root_copy, (events, wins)

    def redact_with_report(self, record):
        """Like :meth:`redact`, also returning a small match report.

        ``bypass`` is true when at least one rule that won a leaf on this
        record was loaded with ``"bypass": true``; ``matched_rules`` lists
        their rule paths in load order.
        """
        check_record(record)
        redacted, (_events, wins) = self._walk(record, want_events=False)
        matched = [self._payloads[order]["path"] for order in sorted(wins)]
        bypass = any(self._payloads[order]["bypass"] for order in wins)
        return redacted, {"bypass": bypass, "matched_rules": matched}

    def _explain_rules(self, record, events):
        winners = {
            event["path"]: event["rule_path"]
            for event in events
            if event["redacted"]
        }
        entries = []
        for payload in self._payloads:
            leaf_paths, containers, reason, miss_count = _resolve_pattern(
                record, payload["segments"]
            )
            won = any(
                winners.get(path) == payload["path"]
                for path in leaf_paths
            )
            entry = {
                "path": payload["path"],
                "mask": payload["mask"],
                "bypass": payload["bypass"],
                "matched_leaves": len(leaf_paths),
                "matched_containers": containers,
                "missed_branches": miss_count,
            }
            if reason is not None:
                entry["status"] = "no-match"
                entry["reason"] = reason
            elif leaf_paths and won:
                entry["status"] = "applied"
            elif leaf_paths:
                entry["status"] = "shadowed"
                entry["reason"] = (
                    "every match is overridden by a more specific or later rule"
                )
            else:
                entry["status"] = "no-match"
                entry["reason"] = (
                    "rule addresses containers only; masks apply to leaves"
                )
            entries.append(entry)
        return entries


def _append_path(path_text, edge):
    """Append one concrete edge to a rendered path (O(1) typical)."""
    if edge[0] == "key":
        if path_text:
            return path_text + "." + edge[1]
        return edge[1]
    return "%s[%d]" % (path_text, edge[1])


def _resolve_pattern(record, segments):
    """Resolve a possibly-wildcard pattern against one record shape.

    Returns ``(leaf_paths, container_count, reason, miss_count)`` where
    ``leaf_paths`` holds rendered concrete path strings:

    * ``container_count`` counts end points that land on dicts/lists
      (masks never apply there);
    * ``reason`` is ``None`` when at least one end point exists,
      otherwise it is the first dead-branch diagnosis in deterministic
      depth-first order (missing key, wrong container, concrete index
      out of range, wildcard over a non-list, wildcard over an empty
      list);
    * ``miss_count`` counts branches that died even though other
      branches matched, so partial matches stay visible.
    """
    leaves = []
    containers = 0
    first_failure = None
    miss_count = 0
    # state: (value, path_text, depth); the path is grown incrementally
    # so even very deep patterns stay linear.
    stack = [(record, "", 0)]

    while stack:
        value, path_text, depth = stack.pop()
        if depth >= len(segments):
            if isinstance(value, (dict, list)):
                containers += 1
            else:
                leaves.append(path_text)
            continue

        kind, token = segments[depth]
        where = path_text if path_text else "<root>"

        if kind == "key":
            if not isinstance(value, dict):
                failure = (
                    "key %r expects a dict under %s but found %s"
                    % (token, where, type(value).__name__)
                )
            elif token not in value:
                failure = "key %r not found under %s" % (token, where)
            else:
                stack.append(
                    (value[token], _append_path(path_text, ("key", token)),
                     depth + 1)
                )
                continue
        elif not isinstance(value, list):
            failure = (
                "index step [%s] expects a list under %s but found %s"
                % (token, where, type(value).__name__)
            )
        elif kind == "index":
            if not 0 <= token < len(value):
                failure = (
                    "index [%d] out of range under %s; list has %d item(s)"
                    % (token, where, len(value))
                )
            else:
                stack.append(
                    (value[token], _append_path(path_text, ("index", token)),
                     depth + 1)
                )
                continue
        elif not value:
            failure = (
                "wildcard [?] matches no items: list under %s is empty"
                % where
            )
        else:
            # Push so that index 0 is explored first under LIFO.
            for index in range(len(value) - 1, -1, -1):
                stack.append(
                    (value[index],
                     _append_path(path_text, ("index", index)), depth + 1)
                )
            continue

        miss_count += 1
        if first_failure is None:
            first_failure = failure

    if leaves or containers:
        return leaves, containers, None, miss_count
    return leaves, containers, first_failure, miss_count
