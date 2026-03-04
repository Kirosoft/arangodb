from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class LogEvent:
    timestamp: str
    level: str
    topic: str
    message: str
    fields: dict[str, object]


class StructuredLogBuffer:
    def __init__(self, capacity: int = 2000) -> None:
        self._events: deque[LogEvent] = deque(maxlen=capacity)

    def emit(self, level: str, topic: str, message: str, **fields: object) -> None:
        self._events.append(
            LogEvent(
                timestamp=datetime.now(UTC).isoformat(),
                level=level,
                topic=topic,
                message=message,
                fields=fields,
            )
        )

    def recent(self, limit: int = 50) -> list[dict[str, object]]:
        events = list(self._events)[-limit:]
        return [
            {
                "timestamp": event.timestamp,
                "level": event.level,
                "topic": event.topic,
                "message": event.message,
                "fields": event.fields,
            }
            for event in events
        ]

    def count(self) -> int:
        return len(self._events)
