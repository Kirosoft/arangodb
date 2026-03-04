from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class RocksDBWalManager:
    wal_dir: Path
    _tick: int = 0
    _history: list[str] = field(default_factory=list)

    def ensure(self) -> None:
        self.wal_dir.mkdir(parents=True, exist_ok=True)

    def record(self, operation: str) -> int:
        self._tick += 1
        line = f"{self._tick}:{operation}"
        self._history.append(line)
        return self._tick

    def flush(self) -> dict:
        self.ensure()
        wal_file = self.wal_dir / "wal.log"
        wal_file.write_text("\n".join(self._history), encoding="utf-8")
        return {"flushed": True, "tick": self._tick, "file": str(wal_file)}

    def current_files(self) -> list[str]:
        self.ensure()
        wal_file = self.wal_dir / "wal.log"
        if wal_file.exists():
            return [str(wal_file)]
        return []

    def current_tick(self) -> int:
        return self._tick
