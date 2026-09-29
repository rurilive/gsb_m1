"""Baseline shortest-path helpers (pre-refactor).

This module holds the current, deliberately naive implementation of a
directed weighted-graph toolkit.  Graphs are stored as adjacency lists of
``(target, weight)`` pairs.  Every shortest-path routine here works by
relaxing *all* edges over and over until a full pass makes no change, so the
number of passes can grow with the number of vertices even on tiny inputs.
There is no priority queue, no path reconstruction and no counting yet --
those are the subject of the requested iteration.
"""


class PathError(Exception):
    """Base class for every error raised by this package."""


def _normalize(adj):
    """Return ``adj`` as a ``dict`` of node -> list of (target, weight)."""
    if adj is None:
        raise PathError("adjacency must not be None")
    out = {}
    for source, edges in adj.items():
        pairs = []
        for edge in edges:
            if len(edge) != 2:
                raise PathError("each edge must be a (target, weight) pair")
            target, weight = edge
            pairs.append((target, weight))
        out[source] = pairs
        # Make sure every target shows up as a key so isolated nodes exist.
        for target, _ in pairs:
            out.setdefault(target, [])
    return out


class NaivePath:
    """A naive, standard-library-only shortest-path helper.

    The graph is a plain dict mapping a node to a list of ``(target, weight)``
    pairs.  Weights are expected to be non-negative; this baseline does not
    actively reject negative weights everywhere, it only offers a scan that
    reports whether any negative edge exists.
    """

    def __init__(self, adj):
        self.adj = _normalize(adj)
        self.nodes = sorted(self.adj.keys(), key=lambda n: (str(type(n)), str(n)))

    # -- graph introspection ------------------------------------------------
    def nodes_list(self):
        """Return the nodes as a sorted list (deterministic order)."""
        return list(self.nodes)

    def edge_count(self):
        """Return how many edges (parallel copies included) are stored."""
        total = 0
        for edges in self.adj.values():
            total += len(edges)
        return total

    def has_negative(self):
        """True if any stored edge carries a negative weight."""
        for edges in self.adj.values():
            for _, weight in edges:
                if weight < 0:
                    return True
        return False

    # -- reachability -------------------------------------------------------
    def path_exists(self, s, t):
        """Return True if ``t`` is reachable from ``s`` (single pass)."""
        self._require(s)
        self._require(t)
        if s == t:
            return True
        seen = {s}
        stack = [s]
        while stack:
            cur = stack.pop()
            for nxt, _ in self.adj.get(cur, ()):
                if nxt == t:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    # -- distances by round-after-round relaxation --------------------------
    def dist_all(self, s):
        """Shortest distances from ``s`` to every reachable node.

        Reachable node -> its distance; unreachable node -> the sentinel
        ``None``.  The source maps to ``0``.  This is the naive relaxation:
        each round sweeps every edge and repeats until a round changes
        nothing, so the round count is bounded only by the vertex count.
        """
        self._require(s)
        dist = {node: None for node in self.adj}
        dist[s] = 0
        changed = True
        while changed:
            changed = False
            for u, edges in self.adj.items():
                if dist[u] is None:
                    continue
                base = dist[u]
                for v, w in edges:
                    candidate = base + w
                    if dist[v] is None or candidate < dist[v]:
                        dist[v] = candidate
                        changed = True
        dist[s] = 0
        return dist

    def shortest(self, s, t):
        """Shortest distance from ``s`` to ``t`` or ``None`` if unreachable."""
        self._require(s)
        self._require(t)
        return self.dist_all(s)[t]

    # -- helpers ------------------------------------------------------------
    def _require(self, node):
        if node not in self.adj:
            raise PathError("unknown node: %r" % (node,))
