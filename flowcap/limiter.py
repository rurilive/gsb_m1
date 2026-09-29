"""Baseline rate limiting primitives.

This module intentionally contains only the most naive limiter we could ship:
:class:`CounterLimiter`. It keeps a single counter of accepted requests and
rejects everything after the configured budget has been used up. There is no
window, no time based recovery, no per-key buckets and no waiting support.
"""


class FlowError(Exception):
    """Base class for every error raised by flowcap."""


class CounterLimiter:
    """A cumulative counter limiter.

    The limiter accepts at most ``limit`` requests over its whole lifetime.
    Once that many requests have been allowed, every further call to
    :meth:`allow` is rejected. No clock is consulted; the counter only ever
    grows.
    """

    def __init__(self, limit):
        if not isinstance(limit, int):
            raise FlowError("limit must be an int")
        if limit < 0:
            raise FlowError("limit must be non-negative")
        self._limit = limit
        self._count = 0

    @property
    def limit(self):
        return self._limit

    @property
    def count(self):
        return self._count

    def allow(self):
        """Record one request and return whether it is allowed.

        Returns ``True`` while fewer than ``limit`` requests have been
        recorded, otherwise ``False``. The internal counter is incremented for
        every call regardless of the outcome, mirroring a plain tally.
        """
        self._count += 1
        return self._count <= self._limit
