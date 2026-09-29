"""Baseline Top-K helper for the rankly package.

The current implementation is intentionally naive: it materializes the whole
input, sorts it in descending order and slices off the first k items.  There is
no heap, no streaming and no incremental state -- memory and time grow with the
full input size.
"""


class SortTopK(object):
    """Compute the top k largest items by sorting the entire input.

    This is the only strategy shipped today.  It accepts an iterable of
    comparable numbers and keeps a full sorted copy of the data.
    """

    def __init__(self, data, k):
        if not isinstance(k, int):
            raise TypeError("k must be an int")
        if k < 0:
            raise ValueError("k must be non-negative")
        self._data = list(data)
        self._k = k

    @property
    def k(self):
        return self._k

    def top(self):
        """Return the k largest items in descending order.

        The result is a plain list.  When k is larger than the number of
        items, the whole sorted sequence is returned.
        """
        ordered = sorted(self._data, reverse=True)
        return ordered[: self._k]

    def size(self):
        """Number of items currently held by this instance."""
        return len(self._data)
