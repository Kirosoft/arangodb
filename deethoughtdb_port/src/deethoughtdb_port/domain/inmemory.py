from __future__ import annotations

import itertools
import uuid

from deethoughtdb_port.domain.interfaces import (
    CatalogService,
    CollectionInfo,
    DatabaseInfo,
    StorageEngine,
    TransactionManager,
)


class InMemoryCatalogService(CatalogService):
    def __init__(self) -> None:
        self._db_id = itertools.count(start=1)
        self._collection_id = itertools.count(start=1)
        self._databases: dict[str, DatabaseInfo] = {}
        self._collections: dict[str, dict[str, CollectionInfo]] = {}

    def create_database(self, name: str) -> DatabaseInfo:
        if name in self._databases:
            return self._databases[name]
        database = DatabaseInfo(database_id=next(self._db_id), name=name)
        self._databases[name] = database
        self._collections[name] = {}
        return database

    def list_databases(self) -> list[DatabaseInfo]:
        return sorted(self._databases.values(), key=lambda item: item.database_id)

    def create_collection(self, database: str, name: str) -> CollectionInfo:
        if database not in self._collections:
            raise KeyError(f"database '{database}' not found")
        existing = self._collections[database].get(name)
        if existing is not None:
            return existing
        collection = CollectionInfo(
            collection_id=next(self._collection_id),
            database=database,
            name=name,
        )
        self._collections[database][name] = collection
        return collection


class InMemoryTransactionManager(TransactionManager):
    def __init__(self) -> None:
        self._active: set[str] = set()

    def begin(self) -> str:
        transaction_id = uuid.uuid4().hex
        self._active.add(transaction_id)
        return transaction_id

    def commit(self, transaction_id: str) -> None:
        self._active.remove(transaction_id)

    def abort(self, transaction_id: str) -> None:
        self._active.remove(transaction_id)


class NoopStorageEngine(StorageEngine):
    def health_check(self) -> dict:
        return {"status": "ok"}

    def get_capabilities(self) -> dict:
        return {
            "aql": False,
            "transactions": True,
            "databases": True,
            "collections": True,
        }
