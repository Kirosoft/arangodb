from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True)
class ValidationArtifactRecorder:
    base_dir: Path
    _events_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self.base_dir / "runtime-events.jsonl"

    def record_request_result(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        api_version: int,
        status_code: int,
        duration_ms: int,
        principal: str,
    ) -> None:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "requestId": request_id,
            "method": method,
            "path": path,
            "apiVersion": api_version,
            "statusCode": status_code,
            "durationMs": duration_ms,
            "principal": principal,
        }
        with self._events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def events_path(self) -> Path:
        return self._events_path
