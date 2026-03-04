from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class RecoveryState(str, Enum):
    BEFORE = "before"
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass(slots=True)
class StorageSnapshot:
    tick: int


class StorageEngineContract(ABC):
    @abstractmethod
    def type_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_capabilities(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_databases(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def create_database(self, name: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def drop_database(self, name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_collection(self, database: str, name: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_collections(self, database: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def drop_collection(self, database: str, name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def insert_document(self, database: str, collection: str, document: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_document(self, database: str, collection: str, key: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def remove_document(self, database: str, collection: str, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def replace_document(self, database: str, collection: str, key: str, document: dict) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def update_document(self, database: str, collection: str, key: str, patch: dict) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def create_index(self, database: str, collection: str, definition: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_indexes(self, database: str, collection: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def create_view(self, database: str, definition: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    def list_views(self, database: str) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def get_view(self, database: str, name: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def drop_view(self, database: str, name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def flush_wal(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def current_wal_files(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def recovery_state(self) -> RecoveryState:
        raise NotImplementedError

    @abstractmethod
    def recovery_tick(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def current_tick(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def release_tick(self, tick: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def current_snapshot(self) -> StorageSnapshot:
        raise NotImplementedError

    @abstractmethod
    def create_replication_applier_config(self, config: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_replication_applier_config(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def remove_replication_applier_config(self) -> None:
        raise NotImplementedError
