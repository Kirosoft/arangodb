from __future__ import annotations

from pathlib import Path
import uuid

from deethoughtdb_port.storage.contracts import (
    RecoveryState,
    StorageEngineContract,
    StorageSnapshot,
)

from .bindings import RocksDBBindings
from .catalog import RocksDBCatalog
from .config import RocksDBPortConfig
from .wal import RocksDBWalManager


class RocksDBEnginePort(StorageEngineContract):
    def __init__(self, config: RocksDBPortConfig) -> None:
        self._config = config
        self._config.base_path.mkdir(parents=True, exist_ok=True)
        self._config.wal_path.mkdir(parents=True, exist_ok=True)

        self._catalog = RocksDBCatalog()
        self._wal = RocksDBWalManager(self._config.wal_path)
        self._bindings = RocksDBBindings()
        self._db = None
        self._released_tick = 0
        self._recovery_state = RecoveryState.DONE
        self._replication_config: dict[str, object] = {}
        self._documents: dict[str, dict[str, dict[str, dict]]] = {}

        if self._bindings.available:
            data_file = Path(self._config.base_path) / "deethoughtdb.rocksdb"
            self._db = self._bindings.open(data_file)

        self.create_database("_system")

    def type_name(self) -> str:
        return "rocksdb"

    def health_check(self) -> dict:
        return {
            "status": "ok",
            "engine": "rocksdb",
            "bindingAvailable": self._bindings.available,
            "recoveryState": self._recovery_state.value,
        }

    def get_capabilities(self) -> dict:
        return {
            "engine": "rocksdb",
            "aql": False,
            "transactions": True,
            "databases": True,
            "collections": True,
            "wal": True,
            "bindingAvailable": self._bindings.available,
        }

    def get_databases(self) -> list[dict]:
        return self._catalog.database_list()

    def create_database(self, name: str) -> dict:
        db = self._catalog.create_database(name)
        self._documents.setdefault(name, {})
        self._wal.record(f"create_database:{name}")
        return db

    def drop_database(self, name: str) -> None:
        self._catalog.drop_database(name)
        self._documents.pop(name, None)
        self._wal.record(f"drop_database:{name}")

    def create_collection(self, database: str, name: str) -> dict:
        col = self._catalog.create_collection(database, name)
        self._documents.setdefault(database, {})
        self._documents[database].setdefault(name, {})
        self._wal.record(f"create_collection:{database}/{name}")
        return col

    def list_collections(self, database: str) -> list[dict]:
        collections = self._catalog.collections.get(database, {})
        return sorted(collections.values(), key=lambda item: item["id"])

    def drop_collection(self, database: str, name: str) -> None:
        self._catalog.drop_collection(database, name)
        if database in self._documents:
            self._documents[database].pop(name, None)
        self._wal.record(f"drop_collection:{database}/{name}")

    def insert_document(self, database: str, collection: str, document: dict) -> dict:
        if database not in self._documents or collection not in self._documents[database]:
            raise KeyError(f"collection '{database}/{collection}' not found")

        stored = dict(document)
        key = str(stored.get("_key", uuid.uuid4().hex))
        stored["_key"] = key
        self._documents[database][collection][key] = stored
        self._wal.record(f"insert_document:{database}/{collection}/{key}")
        return dict(stored)

    def get_document(self, database: str, collection: str, key: str) -> dict | None:
        document = self._documents.get(database, {}).get(collection, {}).get(key)
        if document is None:
            return None
        return dict(document)

    def remove_document(self, database: str, collection: str, key: str) -> bool:
        documents = self._documents.get(database, {}).get(collection)
        if documents is None or key not in documents:
            return False
        documents.pop(key)
        self._wal.record(f"remove_document:{database}/{collection}/{key}")
        return True

    def flush_wal(self) -> dict:
        return self._wal.flush()

    def current_wal_files(self) -> list[str]:
        return self._wal.current_files()

    def recovery_state(self) -> RecoveryState:
        return self._recovery_state

    def recovery_tick(self) -> int:
        return self._wal.current_tick()

    def current_tick(self) -> int:
        return self._wal.current_tick()

    def release_tick(self, tick: int) -> None:
        self._released_tick = max(self._released_tick, tick)

    def current_snapshot(self) -> StorageSnapshot:
        return StorageSnapshot(tick=self.current_tick())

    def create_replication_applier_config(self, config: dict) -> dict:
        self._replication_config.update(config)
        self._wal.record("update_replication_applier")
        return dict(self._replication_config)

    def get_replication_applier_config(self) -> dict:
        return dict(self._replication_config)

    def remove_replication_applier_config(self) -> None:
        self._replication_config = {}
        self._wal.record("remove_replication_applier")
