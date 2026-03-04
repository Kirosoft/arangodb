from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class DatabaseInfo:
    database_id: int
    name: str


@dataclass(slots=True)
class CollectionInfo:
    collection_id: int
    database: str
    name: str


class CatalogService(ABC):
    @abstractmethod
    def create_database(self, name: str) -> DatabaseInfo:
        raise NotImplementedError

    @abstractmethod
    def list_databases(self) -> list[DatabaseInfo]:
        raise NotImplementedError

    @abstractmethod
    def create_collection(self, database: str, name: str) -> CollectionInfo:
        raise NotImplementedError


class StorageEngine(ABC):
    @abstractmethod
    def health_check(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_capabilities(self) -> dict:
        raise NotImplementedError


class TransactionManager(ABC):
    @abstractmethod
    def begin(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def commit(self, transaction_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def abort(self, transaction_id: str) -> None:
        raise NotImplementedError
