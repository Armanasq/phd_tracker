from __future__ import annotations

from collections.abc import Iterable, Iterator


class StreamFormatError(ValueError):
    pass


def sse_events(source: Iterable[bytes], *, max_bytes: int = 2_000_000,
               max_event_bytes: int = 100_000) -> Iterator[tuple[str, str]]:
    total = 0
    kind = "message"
    fields: list[str] = []
    size = 0

    for raw in source:
        if not isinstance(raw, bytes):
            raise StreamFormatError("Expected a byte-oriented event stream")
        total += len(raw)
        if total > max_bytes or len(raw) > max_event_bytes:
            raise StreamFormatError("Streaming response exceeded its byte limit")
        try:
            line = raw.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as error:
            raise StreamFormatError("Streaming response contains invalid UTF-8") from error
        if not line:
            if fields:
                yield kind, "\n".join(fields)
            fields, kind, size = [], "message", 0
        elif line.startswith("data:"):
            value = line[5:].lstrip(" ")
            size += len(value.encode("utf-8"))
            if size > max_event_bytes:
                raise StreamFormatError("Streaming event exceeded its byte limit")
            fields.append(value)
        elif line.startswith("event:"):
            value = line[6:].strip()
            if len(value) > 64 or not all(c.isalnum() or c in "_-" for c in value):
                raise StreamFormatError("Invalid streaming event type")
            kind = value or "message"

    if fields:
        yield kind, "\n".join(fields)
