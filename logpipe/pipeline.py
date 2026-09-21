"""The log pipeline: records in, serialized lines out."""

from .records import check_record, dumps


class LogPipeline:
    """Validate records, serialize them and hand the lines to a sink.

    A pipeline never mutates the record it is given; emitting a record
    twice writes the same two lines. Records that are not dicts raise
    ``TypeError`` before anything reaches the sink.
    """

    def __init__(self, sink):
        if sink is None:
            raise ValueError("a sink is required")
        self.sink = sink
        self.emitted = 0

    def emit(self, record):
        """Write one record, returning the serialized line."""
        check_record(record)
        line = dumps(record)
        self.sink.write(line)
        self.emitted += 1
        return line

    def emit_many(self, records):
        """Emit an iterable of records, returning how many were written."""
        written = 0
        for record in records:
            self.emit(record)
            written += 1
        return written

    def stats(self):
        return {"emitted": self.emitted, "sink": type(self.sink).__name__}
