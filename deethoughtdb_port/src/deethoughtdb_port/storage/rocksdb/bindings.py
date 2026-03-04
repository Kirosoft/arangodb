from __future__ import annotations

from pathlib import Path

from .exceptions import RocksDBBindingUnavailable


class RocksDBBindings:
    def __init__(self) -> None:
        self._rocksdb = None
        try:
            import rocksdb  # type: ignore

            self._rocksdb = rocksdb
        except Exception:
            self._rocksdb = None

    @property
    def available(self) -> bool:
        return self._rocksdb is not None

    def open(self, path: Path):
        if self._rocksdb is None:
            raise RocksDBBindingUnavailable(
                "python rocksdb binding not available; install 'python-rocksdb'"
            )
        opts = self._rocksdb.Options(create_if_missing=True)
        return self._rocksdb.DB(str(path), opts)
