from __future__ import annotations

import itertools
from dataclasses import dataclass, field


@dataclass(slots=True)
class RocksDBCatalog:
    _db_id: itertools.count = field(default_factory=lambda: itertools.count(1))
    _col_id: itertools.count = field(default_factory=lambda: itertools.count(1))
    _idx_id: itertools.count = field(default_factory=lambda: itertools.count(1))
    _view_id: itertools.count = field(default_factory=lambda: itertools.count(1))
    databases: dict[str, dict] = field(default_factory=dict)
    collections: dict[str, dict[str, dict]] = field(default_factory=dict)
    indexes: dict[str, dict[str, list[dict]]] = field(default_factory=dict)
    views: dict[str, dict[str, dict]] = field(default_factory=dict)

    def create_database(self, name: str) -> dict:
        existing = self.databases.get(name)
        if existing is not None:
            return existing
        info = {"id": next(self._db_id), "name": name}
        self.databases[name] = info
        self.collections[name] = {}
        self.indexes[name] = {}
        self.views[name] = {}
        return info

    def drop_database(self, name: str) -> None:
        self.databases.pop(name, None)
        self.collections.pop(name, None)
        self.indexes.pop(name, None)
        self.views.pop(name, None)

    def create_collection(self, database: str, name: str) -> dict:
        if database not in self.collections:
            raise KeyError(f"database '{database}' not found")
        existing = self.collections[database].get(name)
        if existing is not None:
            return existing
        info = {"id": next(self._col_id), "name": name, "database": database}
        self.collections[database][name] = info
        self.indexes[database].setdefault(name, [])
        return info

    def drop_collection(self, database: str, name: str) -> None:
        if database in self.collections:
            self.collections[database].pop(name, None)
            self.indexes[database].pop(name, None)

    def create_index(self, database: str, collection: str, definition: dict) -> dict:
        if database not in self.collections or collection not in self.collections[database]:
            raise KeyError(f"collection '{database}/{collection}' not found")

        index_type = str(definition.get("type", "hash"))
        fields = list(definition.get("fields", []))
        info = {
            "id": f"{collection}/{next(self._idx_id)}",
            "database": database,
            "collection": collection,
            "type": index_type,
            "fields": fields,
            "unique": bool(definition.get("unique", False)),
            "sparse": bool(definition.get("sparse", False)),
        }
        self.indexes[database].setdefault(collection, []).append(info)
        return info

    def list_indexes(self, database: str, collection: str) -> list[dict]:
        if database not in self.collections or collection not in self.collections[database]:
            raise KeyError(f"collection '{database}/{collection}' not found")
        return list(self.indexes[database].get(collection, []))

    def create_view(self, database: str, definition: dict) -> dict:
        if database not in self.views:
            raise KeyError(f"database '{database}' not found")

        name = str(definition.get("name", ""))
        if not name:
            raise ValueError("view creation expects 'name'")

        existing = self.views[database].get(name)
        if existing is not None:
            return existing

        info = {
            "id": next(self._view_id),
            "database": database,
            "name": name,
            "type": str(definition.get("type", "search")),
            "properties": dict(definition.get("properties", {})),
        }
        self.views[database][name] = info
        return info

    def list_views(self, database: str) -> list[dict]:
        if database not in self.views:
            raise KeyError(f"database '{database}' not found")
        return sorted(self.views[database].values(), key=lambda item: item["id"])

    def get_view(self, database: str, name: str) -> dict | None:
        if database not in self.views:
            raise KeyError(f"database '{database}' not found")
        view = self.views[database].get(name)
        if view is None:
            return None
        return dict(view)

    def drop_view(self, database: str, name: str) -> bool:
        if database not in self.views:
            raise KeyError(f"database '{database}' not found")
        removed = self.views[database].pop(name, None)
        return removed is not None

    def database_list(self) -> list[dict]:
        return sorted(self.databases.values(), key=lambda item: item["id"])
