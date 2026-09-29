"""flowcap: a small, dependency-free rate limiting toolkit.

The current release ships a single primitive, :class:`CounterLimiter`, which
tracks how many requests have been seen in total and rejects everything once a
fixed budget has been exhausted. There is no notion of time in this version.
"""

from .limiter import CounterLimiter, FlowError

__all__ = ["CounterLimiter", "FlowError"]
