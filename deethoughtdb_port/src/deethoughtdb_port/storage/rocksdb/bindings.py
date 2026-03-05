from __future__ import annotations

from pathlib import Path


class EmbeddedRocksDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._kv: dict[bytes, bytes] = {}

    def put(self, key: bytes, value: bytes) -> None:
        self._kv[key] = value

    def get(self, key: bytes) -> bytes | None:
        return self._kv.get(key)


class RocksDBBindings:
    def __init__(self) -> None:
        self._embedded_only = True

    @property
    def available(self) -> bool:
        return True

    def open(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        return EmbeddedRocksDB(path)
