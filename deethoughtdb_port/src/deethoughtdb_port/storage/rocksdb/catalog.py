from __future__ import annotations

import itertools
from dataclasses import dataclass, field


@dataclass(slots=True)
class RocksDBCatalog:
    _db_id: itertools.count = field(default_factory=lambda: itertools.count(1))
    _col_id: itertools.count = field(default_factory=lambda: itertools.count(1))
    databases: dict[str, dict] = field(default_factory=dict)
    collections: dict[str, dict[str, dict]] = field(default_factory=dict)

    def create_database(self, name: str) -> dict:
        existing = self.databases.get(name)
        if existing is not None:
            return existing
        info = {"id": next(self._db_id), "name": name}
        self.databases[name] = info
        self.collections[name] = {}
        return info

    def drop_database(self, name: str) -> None:
        self.databases.pop(name, None)
        self.collections.pop(name, None)

    def create_collection(self, database: str, name: str) -> dict:
        if database not in self.collections:
            raise KeyError(f"database '{database}' not found")
        existing = self.collections[database].get(name)
        if existing is not None:
            return existing
        info = {"id": next(self._col_id), "name": name, "database": database}
        self.collections[database][name] = info
        return info

    def drop_collection(self, database: str, name: str) -> None:
        if database in self.collections:
            self.collections[database].pop(name, None)

    def database_list(self) -> list[dict]:
        return sorted(self.databases.values(), key=lambda item: item["id"])
