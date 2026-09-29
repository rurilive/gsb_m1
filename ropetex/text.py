"""Baseline flat text buffer.

The buffer keeps the whole document as one Python string. Insert and delete
work by slicing and re-joining that string. There is no tree, no block
structure, no sharing and no balancing. This is intentionally the naive
reference implementation.
"""


class FlatText:
    """A plain text buffer backed by a single Python string.

    Positions are zero based. Inserts accept any position from 0 to the
    current length inclusive. Deletes accept an empty or in range span.
    """

    def __init__(self, initial=""):
        if not isinstance(initial, str):
            raise TypeError("initial must be a str")
        self._data = initial

    def __len__(self):
        return len(self._data)

    @property
    def length(self):
        return len(self._data)

    def charAt(self, index):
        """Return the character at index, or "" when the index is out of range."""
        if index < 0 or index >= len(self._data):
            return ""
        return self._data[index]

    def substring(self, start, end):
        """Return the text in [start, end), clamped to the buffer bounds."""
        if start < 0:
            start = 0
        if end > len(self._data):
            end = len(self._data)
        if start >= end:
            return ""
        return self._data[start:end]

    def insert(self, pos, text):
        """Insert text at pos and return the new length.

        pos may equal the length (append). pos outside [0, len] is an error.
        """
        if not isinstance(text, str):
            raise TypeError("text must be a str")
        if pos < 0 or pos > len(self._data):
            raise ValueError("insert position out of range")
        self._data = self._data[:pos] + text + self._data[pos:]
        return len(self._data)

    def delete(self, start, end):
        """Delete the text in [start, end) and return the number removed."""
        if start < 0 or end < start or end > len(self._data):
            raise ValueError("delete range out of range")
        removed = end - start
        self._data = self._data[:start] + self._data[end:]
        return removed

    def toString(self):
        return self._data

    def __str__(self):
        return self._data

    def __repr__(self):
        return "FlatText(%r)" % (self._data,)
