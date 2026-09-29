"""Baseline mutable sequence for persistx.

MutList is the naive, pre-refactor implementation: a single Python list is
kept in place, every mutation edits that one list directly, and a snapshot
can only be taken by copying the whole list by hand. There is no version
handle, no structural sharing and no node-reuse accounting here.
"""


class MutList:
    """A plain mutable list wrapper.

    The whole point of the baseline is that it is not persistent: modifying
    the list changes the instance itself, and any previously taken snapshot
    must have been copied out beforehand.
    """

    def __init__(self, items=None):
        if items is None:
            self._data = []
        else:
            self._data = list(items)

    def push(self, x):
        """Append x at the tail and return self."""
        self._data.append(x)
        return self

    def pop(self):
        """Remove and return the tail element.

        Raises IndexError when the list is empty.
        """
        if not self._data:
            raise IndexError("pop from empty list")
        return self._data.pop()

    def set(self, i, v):
        """Set the value at index i and return self.

        Raises IndexError when i is out of range.
        """
        n = len(self._data)
        if i < 0 or i >= n:
            raise IndexError("list assignment index out of range")
        self._data[i] = v
        return self

    def get(self, i):
        """Return the value at index i.

        Raises IndexError when i is out of range.
        """
        n = len(self._data)
        if i < 0 or i >= n:
            raise IndexError("list index out of range")
        return self._data[i]

    def snapshot(self):
        """Return a shallow copy of the current list."""
        return list(self._data)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __eq__(self, other):
        if isinstance(other, MutList):
            return self._data == other._data
        return NotImplemented

    def __repr__(self):
        return "MutList(%r)" % (self._data,)
