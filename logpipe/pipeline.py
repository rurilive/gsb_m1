"""The log pipeline: records in, serialized lines out."""

from .records import check_record, dumps


def _is_redactor(obj):
    return hasattr(obj, "redact") and callable(getattr(obj, "redact"))


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
        self._redactor = None
        self._bypass_sink = None

    def set_redactor(self, redactor):
        """Attach a :class:`~logpipe.redact.Redactor` (or detach with None).

        Attachment takes effect immediately for every subsequent
        :meth:`emit`, including rule hot reloads performed on the same
        redactor instance. With no redactor attached records are emitted
        exactly as given.
        """
        if redactor is not None and not _is_redactor(redactor):
            raise TypeError(
                "redactor must expose a redact() method, got %s"
                % type(redactor).__name__
            )
        self._redactor = redactor
        return redactor

    def set_bypass_sink(self, sink):
        """Set the sink that receives original (unredacted) records.

        The original record is only written when a rule that actually
        matched the record carries ``"bypass": true``; by default
        originals never land anywhere. Pass ``None`` to disable.
        """
        self._bypass_sink = sink
        return sink

    def emit(self, record):
        """Write one record, returning the serialized line."""
        check_record(record)
        if self._redactor is None:
            line = dumps(record)
        elif self._bypass_sink is None:
            line = dumps(self._redactor.redact(record))
        else:
            redacted, report = self._redactor.redact_with_report(record)
            line = dumps(redacted)
            if report["bypass"]:
                self._bypass_sink.write(dumps(record))
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
        return {
            "emitted": self.emitted,
            "sink": type(self.sink).__name__,
            "redactor": type(self._redactor).__name__ if self._redactor else None,
            "bypass_sink": (
                type(self._bypass_sink).__name__ if self._bypass_sink else None
            ),
        }
