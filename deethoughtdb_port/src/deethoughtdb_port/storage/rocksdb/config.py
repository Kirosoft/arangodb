from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RocksDBPortConfig:
    base_path: Path
    wal_path: Path
    create_if_missing: bool = True

    @staticmethod
    def from_root(root: str | Path) -> "RocksDBPortConfig":
        base = Path(root)
        return RocksDBPortConfig(base_path=base / "data", wal_path=base / "wal")
