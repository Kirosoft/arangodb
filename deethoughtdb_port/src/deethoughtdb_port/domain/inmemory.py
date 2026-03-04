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


class InMemoryJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}

    def create(self, payload: dict | None = None, status: str = "done") -> dict:
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "status": status,
            "payload": dict(payload or {}),
        }
        self._jobs[job_id] = job
        return dict(job)

    def get(self, job_id: str) -> dict | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return dict(job)

    def list_ids(self, status: str | None = None) -> list[str]:
        jobs = self._jobs.values()
        if status is not None:
            jobs = [job for job in jobs if job.get("status") == status]
        return [str(job["id"]) for job in jobs]

    def delete(self, job_id: str) -> bool:
        removed = self._jobs.pop(job_id, None)
        return removed is not None


class InMemoryTaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}

    def create(self, task: dict) -> dict:
        task_id = str(task.get("id") or uuid.uuid4().hex)
        payload = {
            "id": task_id,
            "name": str(task.get("name", "task")),
            "command": str(task.get("command", "")),
            "params": dict(task.get("params", {})),
            "period": task.get("period"),
            "offset": task.get("offset"),
        }
        self._tasks[task_id] = payload
        return dict(payload)

    def list(self) -> list[dict]:
        return [dict(task) for task in self._tasks.values()]

    def get(self, task_id: str) -> dict | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return dict(task)

    def delete(self, task_id: str) -> bool:
        removed = self._tasks.pop(task_id, None)
        return removed is not None


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
