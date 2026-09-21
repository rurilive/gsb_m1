"""Sinks that serialized log lines are written to."""

import os


class MemorySink:
    """Collects lines in memory, handy for tests and dry runs."""

    def __init__(self):
        self.lines = []
        self._closed = False

    @property
    def closed(self):
        return self._closed

    def write(self, line):
        if self._closed:
            raise ValueError("sink is already closed")
        if not isinstance(line, str):
            raise TypeError("line must be a string, got %s" % type(line).__name__)
        self.lines.append(line)

    def close(self):
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


class JsonlFileSink:
    """Appends one JSON line per record to a text file."""

    def __init__(self, path, fsync=False):
        self.path = path
        self.count = 0
        self._fsync = fsync
        self._closed = False
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        self._handle = open(path, "a", encoding="utf-8")

    @property
    def closed(self):
        return self._closed

    def write(self, line):
        if self._closed:
            raise ValueError("sink is already closed")
        if not isinstance(line, str):
            raise TypeError("line must be a string, got %s" % type(line).__name__)
        self._handle.write(line)
        self._handle.write("\n")
        self.count += 1
        if self._fsync:
            self.flush()

    def flush(self):
        self._handle.flush()

    def close(self):
        if not self._closed:
            self._handle.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False
