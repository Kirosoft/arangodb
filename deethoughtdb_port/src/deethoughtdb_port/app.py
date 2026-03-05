from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from datetime import datetime, timezone
from uuid import uuid4

from deethoughtdb_port.api.errors import ApiError, bad_request, forbidden, unauthorized
from deethoughtdb_port.domain.auth import AuthService
from deethoughtdb_port.domain.inmemory import (
    InMemoryJobManager,
    InMemoryTaskManager,
    InMemoryTransactionManager,
)
from deethoughtdb_port.domain.distributed import ClusterService, ReplicationService
from deethoughtdb_port.observability import StructuredLogBuffer, ValidationArtifactRecorder
from deethoughtdb_port.runtime.feature import Feature
from deethoughtdb_port.runtime.server import ApplicationServer
from deethoughtdb_port.storage import RocksDBEnginePort, RocksDBPortConfig
from deethoughtdb_port.transport.http_models import HttpRequest, HttpResponse
from deethoughtdb_port.transport.rest_factory import RestHandlerFactory
from deethoughtdb_port.transport.rest_handler import RestHandler


class VersionHandler(RestHandler):
    def handle(self, request: HttpRequest) -> HttpResponse:
        body = {
            "server": "deethoughtdb",
            "apiVersion": request.api_version,
            "path": request.path,
            "details": {
                "engine": "rocksdb",
                "aql": False,
                "phase": "backend-port",
            },
        }
        if request.path == "/_admin/version":
            body["version"] = "0.1.0-port"
            body["license"] = "Apache-2.0"
            body["build"] = {"mode": "debug", "architecture": "x64"}
        return HttpResponse(
            status_code=200,
            body=body,
        )


class AqlDisabledHandler(RestHandler):
    def handle(self, _request: HttpRequest) -> HttpResponse:
        return HttpResponse(
            status_code=501,
            body={
                "error": True,
                "code": 501,
                "errorNum": 501,
                "errorMessage": "AQL/query endpoints are disabled in this port phase",
                "capability": "aql-disabled",
            },
        )


class CatchAllHandler(RestHandler):
    def handle(self, request: HttpRequest) -> HttpResponse:
        return HttpResponse(
            status_code=404,
            body={
                "error": True,
                "code": 404,
                "errorNum": 404,
                "errorMessage": f"no route for '{request.path}'",
                "prefix": request.prefix,
                "suffixes": request.suffixes,
            },
        )


class DatabaseHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method == "GET":
            databases = self._storage.get_databases()
            return HttpResponse(status_code=200, body={"result": databases})

        if request.method == "POST":
            if not isinstance(request.body, dict) or "name" not in request.body:
                raise bad_request("database creation expects body {'name': '<db-name>'}")
            database = self._storage.create_database(str(request.body["name"]))
            return HttpResponse(
                status_code=201,
                body={"result": database},
            )

        if request.method == "DELETE" and len(request.suffixes) == 1:
            self._storage.drop_database(request.suffixes[0])
            return HttpResponse(status_code=200, body={"result": {"dropped": request.suffixes[0]}})

        raise bad_request(f"unsupported method '{request.method}' for /_api/database")


class EngineHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            raise bad_request("/_api/engine expects GET")

        if len(request.suffixes) == 1 and request.suffixes[0] == "stats":
            health = self._storage.health_check()
            return HttpResponse(
                status_code=200,
                body={
                    "result": {
                        "engine": self._storage.type_name(),
                        "status": health.get("status", "unknown"),
                        "recoveryState": health.get("recoveryState", "unknown"),
                        "currentTick": self._storage.current_tick(),
                    }
                },
            )

        if len(request.suffixes) > 0:
            raise bad_request("unsupported engine path")

        return HttpResponse(
            status_code=200,
            body={
                "name": self._storage.type_name(),
                "supports": self._storage.get_capabilities(),
            },
        )


class CollectionHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        database = _resolve_database_from_path(request)

        if request.method == "GET":
            if len(request.suffixes) == 1:
                collection = self._storage.get_collection(database, request.suffixes[0])
                if collection is None:
                    return HttpResponse(
                        status_code=404,
                        body={
                            "error": True,
                            "code": 404,
                            "errorNum": 404,
                            "errorMessage": f"collection '{request.suffixes[0]}' not found",
                        },
                    )
                return HttpResponse(status_code=200, body={"result": collection})

            if len(request.suffixes) == 2 and request.suffixes[1] == "count":
                collection = self._storage.get_collection(database, request.suffixes[0])
                if collection is None:
                    return HttpResponse(
                        status_code=404,
                        body={
                            "error": True,
                            "code": 404,
                            "errorNum": 404,
                            "errorMessage": f"collection '{request.suffixes[0]}' not found",
                        },
                    )
                return HttpResponse(
                    status_code=200,
                    body={
                        "result": {
                            "name": request.suffixes[0],
                            "count": self._storage.count_documents(database, request.suffixes[0]),
                        }
                    },
                )

            return HttpResponse(
                status_code=200,
                body={"result": self._storage.list_collections(database)},
            )

        if request.method == "POST":
            if not isinstance(request.body, dict) or "name" not in request.body:
                raise bad_request("collection creation expects body {'name': '<collection-name>'}")
            try:
                collection = self._storage.create_collection(database, str(request.body["name"]))
            except KeyError as exc:
                raise bad_request(str(exc)) from exc
            return HttpResponse(status_code=201, body={"result": collection})

        if request.method == "DELETE" and len(request.suffixes) == 1:
            self._storage.drop_collection(database, request.suffixes[0])
            return HttpResponse(
                status_code=200,
                body={"result": {"dropped": request.suffixes[0], "database": database}},
            )

        if request.method in {"PUT", "POST"} and len(request.suffixes) == 2 and request.suffixes[1] == "truncate":
            collection_name = request.suffixes[0]
            try:
                removed = self._storage.truncate_collection(database, collection_name)
            except KeyError:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"collection '{collection_name}' not found",
                    },
                )
            return HttpResponse(
                status_code=200,
                body={"result": {"name": collection_name, "truncated": True, "removed": removed}},
            )

        raise bad_request("unsupported collection path")


class DocumentHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        database = _resolve_database_from_path(request)

        if request.method == "POST" and len(request.suffixes) >= 1:
            collection = request.suffixes[0]
            if not isinstance(request.body, dict):
                raise bad_request("document insert expects JSON object")
            try:
                inserted = self._storage.insert_document(database, collection, request.body)
            except KeyError as exc:
                raise bad_request(str(exc)) from exc
            return self._document_response(201, inserted)

        if request.method == "GET" and len(request.suffixes) >= 2:
            collection, key = request.suffixes[0], request.suffixes[1]
            document = self._storage.get_document(database, collection, key)
            if document is None:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"document '{collection}/{key}' not found",
                    },
                )
            return self._document_response(200, document)

        if request.method == "DELETE" and len(request.suffixes) >= 2:
            collection, key = request.suffixes[0], request.suffixes[1]
            existing = self._storage.get_document(database, collection, key)
            if existing is None:
                return self._document_not_found(collection, key)
            rev_error = self._check_revision_precondition(request, None, existing)
            if rev_error is not None:
                return rev_error
            removed = self._storage.remove_document(database, collection, key)
            if not removed:
                return self._document_not_found(collection, key)
            return HttpResponse(status_code=200, body={"result": {"removed": key}})

        if request.method == "PUT" and len(request.suffixes) >= 2:
            collection, key = request.suffixes[0], request.suffixes[1]
            if not isinstance(request.body, dict):
                raise bad_request("document replace expects JSON object")
            existing = self._storage.get_document(database, collection, key)
            if existing is None:
                return self._document_not_found(collection, key)
            rev_error = self._check_revision_precondition(request, request.body, existing)
            if rev_error is not None:
                return rev_error
            replaced = self._storage.replace_document(database, collection, key, request.body)
            if replaced is None:
                return self._document_not_found(collection, key)
            return self._document_response(200, replaced)

        if request.method == "PATCH" and len(request.suffixes) >= 2:
            collection, key = request.suffixes[0], request.suffixes[1]
            if not isinstance(request.body, dict):
                raise bad_request("document update expects JSON object")
            existing = self._storage.get_document(database, collection, key)
            if existing is None:
                return self._document_not_found(collection, key)
            rev_error = self._check_revision_precondition(request, request.body, existing)
            if rev_error is not None:
                return rev_error
            updated = self._storage.update_document(database, collection, key, request.body)
            if updated is None:
                return self._document_not_found(collection, key)
            return self._document_response(200, updated)

        raise bad_request("unsupported document path")

    @staticmethod
    def _document_not_found(collection: str, key: str) -> HttpResponse:
        return HttpResponse(
            status_code=404,
            body={
                "error": True,
                "code": 404,
                "errorNum": 404,
                "errorMessage": f"document '{collection}/{key}' not found",
            },
        )

    @staticmethod
    def _revision_mismatch() -> HttpResponse:
        return HttpResponse(
            status_code=412,
            body={
                "error": True,
                "code": 412,
                "errorNum": 412,
                "errorMessage": "document revision mismatch",
            },
        )

    @staticmethod
    def _document_response(status_code: int, document: dict) -> HttpResponse:
        revision = document.get("_rev")
        headers: dict[str, str] = {}
        if isinstance(revision, str) and revision:
            headers["etag"] = revision
        return HttpResponse(status_code=status_code, body={"result": document}, headers=headers)

    def _check_revision_precondition(
        self,
        request: HttpRequest,
        body: dict | None,
        existing: dict,
    ) -> HttpResponse | None:
        expected = self._expected_revision(request, body)
        if expected is None:
            return None

        current = existing.get("_rev")
        if not isinstance(current, str) or current != expected:
            return self._revision_mismatch()
        return None

    @staticmethod
    def _expected_revision(request: HttpRequest, body: dict | None) -> str | None:
        header = request.headers.get("if-match") or request.headers.get("If-Match")
        if isinstance(header, str) and header:
            return header.strip().strip('"')
        if body is None:
            return None
        body_rev = body.get("_rev")
        if isinstance(body_rev, str) and body_rev:
            return body_rev
        return None


class EdgesHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        database = _resolve_database_from_path(request)

        if request.method == "POST" and len(request.suffixes) >= 1:
            collection = request.suffixes[0]
            if not isinstance(request.body, dict):
                raise bad_request("edge insert expects JSON object")
            edge_from = request.body.get("_from")
            edge_to = request.body.get("_to")
            if not isinstance(edge_from, str) or not isinstance(edge_to, str):
                raise bad_request("edge insert requires string '_from' and '_to'")
            try:
                inserted = self._storage.insert_document(database, collection, request.body)
            except KeyError as exc:
                raise bad_request(str(exc)) from exc
            return HttpResponse(status_code=201, body={"result": inserted})

        if request.method == "GET" and len(request.suffixes) >= 2:
            collection, key = request.suffixes[0], request.suffixes[1]
            edge = self._storage.get_document(database, collection, key)
            if edge is None or "_from" not in edge or "_to" not in edge:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"edge '{collection}/{key}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": edge})

        raise bad_request("unsupported edges path")


class ImportHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        database = _resolve_database_from_path(request)

        if request.method != "POST":
            raise bad_request("import API expects POST")

        collection = request.suffixes[0] if len(request.suffixes) >= 1 else ""
        documents: list[dict] = []

        if isinstance(request.body, list):
            documents = [item for item in request.body if isinstance(item, dict)]
        elif isinstance(request.body, dict):
            if not collection:
                candidate = request.body.get("collection")
                if isinstance(candidate, str):
                    collection = candidate
            payload_docs = request.body.get("documents")
            if isinstance(payload_docs, list):
                documents = [item for item in payload_docs if isinstance(item, dict)]

        if not collection:
            raise bad_request("import expects collection in path or body")
        if not documents:
            raise bad_request("import expects non-empty document list")

        created = 0
        errors = 0
        for document in documents:
            try:
                self._storage.insert_document(database, collection, document)
                created += 1
            except KeyError:
                errors += 1

        return HttpResponse(
            status_code=201 if errors == 0 else 202,
            body={
                "result": {
                    "collection": collection,
                    "created": created,
                    "errors": errors,
                }
            },
        )


class IndexHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        database = _resolve_database_from_path(request)

        if request.method == "POST":
            if not isinstance(request.body, dict):
                raise bad_request("index creation expects JSON object")
            collection = request.body.get("collection")
            if not isinstance(collection, str) or not collection:
                raise bad_request("index creation expects 'collection' in body")
            try:
                index_info = self._storage.create_index(database, collection, request.body)
            except KeyError as exc:
                raise bad_request(str(exc)) from exc
            return HttpResponse(status_code=201, body={"result": index_info})

        if request.method == "GET" and len(request.suffixes) == 1:
            collection = request.suffixes[0]
            try:
                indexes = self._storage.list_indexes(database, collection)
            except KeyError as exc:
                raise bad_request(str(exc)) from exc
            return HttpResponse(status_code=200, body={"result": indexes})

        raise bad_request("unsupported index path")


class ViewHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        database = _resolve_database_from_path(request)

        if request.method == "POST":
            if not isinstance(request.body, dict):
                raise bad_request("view creation expects JSON object")
            if "name" not in request.body:
                raise bad_request("view creation expects 'name' in body")
            try:
                view_info = self._storage.create_view(database, request.body)
            except (KeyError, ValueError) as exc:
                raise bad_request(str(exc)) from exc
            return HttpResponse(status_code=201, body={"result": view_info})

        if request.method == "GET" and len(request.suffixes) == 0:
            try:
                views = self._storage.list_views(database)
            except KeyError as exc:
                raise bad_request(str(exc)) from exc
            return HttpResponse(status_code=200, body={"result": views})

        if request.method == "GET" and len(request.suffixes) == 1:
            view = self._storage.get_view(database, request.suffixes[0])
            if view is None:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"view '{request.suffixes[0]}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": view})

        if request.method == "DELETE" and len(request.suffixes) == 1:
            removed = self._storage.drop_view(database, request.suffixes[0])
            if not removed:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"view '{request.suffixes[0]}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": {"dropped": request.suffixes[0]}})

        raise bad_request("unsupported view path")


class TransactionHandler(RestHandler):
    def __init__(self, manager: InMemoryTransactionManager) -> None:
        self._manager = manager

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and request.path == "/_api/transaction/begin":
            transaction_id = self._manager.begin()
            return HttpResponse(status_code=201, body={"result": {"id": transaction_id}})

        if request.method == "PUT" and request.prefix == "/_api/transaction" and len(request.suffixes) == 1:
            transaction_id = request.suffixes[0]
            try:
                self._manager.commit(transaction_id)
            except KeyError as exc:
                raise bad_request(f"unknown transaction id '{transaction_id}'") from exc
            return HttpResponse(
                status_code=200,
                body={"result": {"id": transaction_id, "status": "commit"}},
            )

        if request.method == "POST" and (
            request.prefix == "/_api/transaction"
            and len(request.suffixes) == 2
            and request.suffixes[1] in {"commit", "abort"}
        ):
            transaction_id, action = request.suffixes
            try:
                if action == "commit":
                    self._manager.commit(transaction_id)
                else:
                    self._manager.abort(transaction_id)
            except KeyError as exc:
                raise bad_request(f"unknown transaction id '{transaction_id}'") from exc
            return HttpResponse(
                status_code=200,
                body={"result": {"id": transaction_id, "status": action}},
            )

        raise bad_request("unsupported transaction path")


class OpenAuthHandler(RestHandler):
    def __init__(self, auth: AuthService) -> None:
        self._auth = auth

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            raise bad_request("/_open/auth expects POST")
        if not isinstance(request.body, dict):
            raise bad_request("/_open/auth expects JSON body")

        username = str(request.body.get("username", ""))
        password = str(request.body.get("password", ""))
        ttl = request.body.get("ttl")
        ttl_seconds: int | None = None
        if ttl is not None:
            try:
                ttl_seconds = int(ttl)
            except (TypeError, ValueError) as exc:
                raise bad_request("/_open/auth ttl must be an integer") from exc
        if not username or not password:
            raise bad_request("/_open/auth requires username and password")

        token = self._auth.authenticate(username, password, ttl_seconds=ttl_seconds)
        if token is None:
            raise unauthorized("invalid credentials")
        result = {"token": token}
        if ttl_seconds is not None:
            result["expiresIn"] = max(0, ttl_seconds)
        return HttpResponse(status_code=200, body={"result": result})


class TokenHandler(RestHandler):
    def __init__(self, auth: AuthService) -> None:
        self._auth = auth

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            raise bad_request("/_api/token expects POST")
        if not isinstance(request.body, dict):
            raise bad_request("/_api/token expects JSON body")

        username = str(request.body.get("username", ""))
        password = str(request.body.get("password", ""))
        ttl = request.body.get("ttl")
        ttl_seconds: int | None = None
        if ttl is not None:
            try:
                ttl_seconds = int(ttl)
            except (TypeError, ValueError) as exc:
                raise bad_request("/_api/token ttl must be an integer") from exc
        if not username or not password:
            raise bad_request("/_api/token requires username and password")

        token = self._auth.authenticate(username, password, ttl_seconds=ttl_seconds)
        if token is None:
            raise unauthorized("invalid credentials")
        result = {"token": token, "jwt": token}
        if ttl_seconds is not None:
            result["expiresIn"] = max(0, ttl_seconds)
        return HttpResponse(status_code=200, body={"result": result})


class UserHandler(RestHandler):
    def __init__(self, auth: AuthService) -> None:
        self._auth = auth

    def handle(self, request: HttpRequest) -> HttpResponse:
        principal = request.headers.get("x-principal", "")
        if not principal or not self._auth.is_admin(principal):
            raise forbidden("admin privileges required")

        if request.method == "GET" and len(request.suffixes) == 0:
            return HttpResponse(status_code=200, body={"result": self._auth.list_users()})

        if request.method == "POST" and len(request.suffixes) == 0:
            if not isinstance(request.body, dict):
                raise bad_request("user creation expects JSON object")
            username = str(request.body.get("user", ""))
            password = str(request.body.get("passwd", ""))
            if not username or not password:
                raise bad_request("user creation expects 'user' and 'passwd'")
            is_admin = bool(request.body.get("isAdmin", False))
            self._auth.create_user(username, password, is_admin=is_admin)
            return HttpResponse(
                status_code=201,
                body={
                    "result": {
                        "user": username,
                        "active": True,
                        "extra": {},
                        "isAdmin": is_admin,
                    }
                },
            )

        if request.method == "DELETE" and len(request.suffixes) == 1:
            username = request.suffixes[0]
            if username == "root":
                raise bad_request("cannot delete root user")
            removed = self._auth.remove_user(username)
            if not removed:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"user '{username}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": {"user": username, "deleted": True}})

        raise bad_request("unsupported user path")


class AdminStatusHandler(RestHandler):
    def __init__(self, app_server: ApplicationServer) -> None:
        self._app_server = app_server

    def handle(self, _request: HttpRequest) -> HttpResponse:
        return HttpResponse(
            status_code=200,
            body={
                "server": "deethoughtdb",
                "status": "running" if self._app_server.is_running else "stopped",
                "startupOrder": self._app_server.startup_order,
            },
        )


class AdminTimeHandler(RestHandler):
    def handle(self, _request: HttpRequest) -> HttpResponse:
        now = datetime.now(tz=timezone.utc)
        return HttpResponse(
            status_code=200,
            body={
                "result": {
                    "utc": now.isoformat(),
                    "timestamp": int(now.timestamp()),
                }
            },
        )


class AdminCompactHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "PUT":
            raise bad_request("/_admin/compact expects PUT")
        flushed = self._storage.flush_wal()
        return HttpResponse(
            status_code=200,
            body={"result": {"compacted": True, "flush": flushed}},
        )


class AdminShutdownHandler(RestHandler):
    def __init__(self, app_server: ApplicationServer) -> None:
        self._app_server = app_server

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            raise bad_request("/_admin/shutdown expects POST")
        self._app_server.shutdown()
        return HttpResponse(status_code=200, body={"result": {"shutdown": True}})


class AdminMetricsHandler(RestHandler):
    def __init__(self, metrics: dict[str, object]) -> None:
        self._metrics = metrics

    def handle(self, _request: HttpRequest) -> HttpResponse:
        return HttpResponse(
            status_code=200,
            body={
                "result": {
                    "requestsTotal": self._metrics["requests_total"],
                    "responsesByStatus": self._metrics["responses_by_status"],
                    "requestsByPath": self._metrics["requests_by_path"],
                    "latencyByPathMs": self._metrics["latency_by_path_ms"],
                }
            },
        )


class AdminLogHandler(RestHandler):
    def __init__(self, logger: StructuredLogBuffer) -> None:
        self._logger = logger

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            raise bad_request("/_admin/log expects GET")
        return HttpResponse(
            status_code=200,
            body={"result": {"count": self._logger.count(), "messages": self._logger.recent(limit=100)}},
        )


class AdminServerHandler(RestHandler):
    def __init__(self, app_server: ApplicationServer, storage: RocksDBEnginePort, cluster: ClusterService) -> None:
        self._app_server = app_server
        self._storage = storage
        self._cluster = cluster

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            raise bad_request("/_admin/server expects GET")
        return HttpResponse(
            status_code=200,
            body={
                "result": {
                    "server": "deethoughtdb",
                    "status": "running" if self._app_server.is_running else "stopped",
                    "engine": self._storage.type_name(),
                    "role": self._cluster.role(),
                    "clusterEnabled": self._cluster.enabled,
                }
            },
        )


class AdminServerIdHandler(RestHandler):
    def __init__(self, cluster: ClusterService) -> None:
        self._cluster = cluster

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            raise bad_request("/_admin/server/id expects GET")
        server_id = "CRDN-1" if self._cluster.enabled else "SNGLE-1"
        return HttpResponse(status_code=200, body={"id": server_id})


class AdminStatisticsHandler(RestHandler):
    def __init__(self, metrics: dict[str, object]) -> None:
        self._metrics = metrics

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            raise bad_request("/_admin/statistics expects GET")

        requests_total = int(self._metrics["requests_total"])
        by_status = dict(self._metrics["responses_by_status"])
        by_path = dict(self._metrics["requests_by_path"])
        latency = dict(self._metrics["latency_by_path_ms"])

        return HttpResponse(
            status_code=200,
            body={
                "result": {
                    "requestsTotal": requests_total,
                    "responsesByStatus": by_status,
                    "requestsByPath": by_path,
                    "latencyByPathMs": latency,
                    "pathsTracked": len(by_path),
                }
            },
        )


class AdminStatisticsDescriptionHandler(RestHandler):
    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            raise bad_request("/_admin/statistics-description expects GET")

        return HttpResponse(
            status_code=200,
            body={
                "groups": {
                    "system": {
                        "name": "system",
                        "description": "General server runtime metrics",
                    },
                    "http": {
                        "name": "http",
                        "description": "HTTP request and response counters",
                    },
                },
                "figures": {
                    "requestsTotal": {
                        "group": "http",
                        "description": "Total number of handled requests",
                        "type": "number",
                    },
                    "responsesByStatus": {
                        "group": "http",
                        "description": "Response counters by status code",
                        "type": "object",
                    },
                    "pathsTracked": {
                        "group": "http",
                        "description": "Number of request paths tracked in metrics",
                        "type": "number",
                    },
                },
            },
        )


class AdminOptionsHandler(RestHandler):
    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            raise bad_request("/_admin/options expects GET")
        return HttpResponse(
            status_code=200,
            body={
                "result": {
                    "server.authentication": True,
                    "database.force-sync-properties": False,
                    "rocksdb.sync-interval": 1000,
                }
            },
        )


class AdminOptionsDescriptionHandler(RestHandler):
    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            raise bad_request("/_admin/options-description expects GET")
        return HttpResponse(
            status_code=200,
            body={
                "result": {
                    "server.authentication": {
                        "type": "boolean",
                        "description": "Enable or disable authentication",
                    },
                    "database.force-sync-properties": {
                        "type": "boolean",
                        "description": "Force sync for database property writes",
                    },
                    "rocksdb.sync-interval": {
                        "type": "number",
                        "description": "WAL sync interval in milliseconds",
                    },
                }
            },
        )


class AdminSystemReportHandler(RestHandler):
    def __init__(
        self,
        app_server: ApplicationServer,
        metrics: dict[str, object],
        logger: StructuredLogBuffer,
        artifact_recorder: ValidationArtifactRecorder,
    ) -> None:
        self._app_server = app_server
        self._metrics = metrics
        self._logger = logger
        self._artifact_recorder = artifact_recorder

    def handle(self, _request: HttpRequest) -> HttpResponse:
        return HttpResponse(
            status_code=200,
            body={
                "result": {
                    "serverStatus": "running" if self._app_server.is_running else "stopped",
                    "startupOrder": self._app_server.startup_order,
                    "metrics": {
                        "requestsTotal": self._metrics["requests_total"],
                        "responsesByStatus": self._metrics["responses_by_status"],
                        "requestsByPath": self._metrics["requests_by_path"],
                        "latencyByPathMs": self._metrics["latency_by_path_ms"],
                    },
                    "logs": {
                        "count": self._logger.count(),
                        "recent": self._logger.recent(limit=20),
                    },
                    "artifacts": {
                        "runtimeEventsPath": str(self._artifact_recorder.events_path()),
                    },
                }
            },
        )


class AdminRoutingReloadHandler(RestHandler):
    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            raise bad_request("/_admin/routing/reload expects POST")
        return HttpResponse(
            status_code=200,
            body={"result": {"routesReloaded": True}},
        )


class ReplicationHandler(RestHandler):
    def __init__(self, replication: ReplicationService, storage: RocksDBEnginePort) -> None:
        self._replication = replication
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method == "GET" and request.path == "/_api/replication/state":
            state = self._replication.state()
            return HttpResponse(
                status_code=200,
                body={
                    "result": {
                        "mode": state.mode,
                        "applierEnabled": state.applier_enabled,
                        "lastTick": state.last_tick,
                    }
                },
            )

        if request.method == "GET" and request.path == "/_api/replication/logger-state":
            state = self._replication.state()
            return HttpResponse(
                status_code=200,
                body={
                    "result": {
                        "running": state.applier_enabled,
                        "lastUncommittedLogTick": state.last_tick,
                        "lastCommittedLogTick": state.last_tick,
                    }
                },
            )

        if request.method == "GET" and request.path == "/_api/replication/applier-state":
            return HttpResponse(
                status_code=200,
                body={"result": self._replication.applier_state()},
            )

        if request.method == "GET" and request.path == "/_api/replication/server-id":
            return HttpResponse(
                status_code=200,
                body={"serverId": self._replication.server_id()},
            )

        if request.method == "POST" and request.path == "/_api/replication/sync":
            return HttpResponse(
                status_code=200,
                body={"result": self._replication.sync()},
            )

        if request.path == "/_api/replication/applier-config":
            if request.method == "GET":
                return HttpResponse(
                    status_code=200,
                    body={"result": self._storage.get_replication_applier_config()},
                )
            if request.method == "PUT":
                if not isinstance(request.body, dict):
                    raise bad_request("replication applier config expects JSON object")
                self._replication.update_applier_config(request.body)
                updated = self._storage.create_replication_applier_config(request.body)
                return HttpResponse(status_code=200, body={"result": updated})
            if request.method == "DELETE":
                self._replication.clear_applier_config()
                self._storage.remove_replication_applier_config()
                return HttpResponse(status_code=200, body={"result": {"deleted": True}})

        if request.path == "/_api/replication/applier-start" and request.method == "PUT":
            state = self._replication.start_applier()
            return HttpResponse(
                status_code=200,
                body={
                    "result": {
                        "running": state.applier_enabled,
                        "lastTick": state.last_tick,
                    }
                },
            )

        if request.path == "/_api/replication/applier-stop" and request.method == "PUT":
            state = self._replication.stop_applier()
            return HttpResponse(
                status_code=200,
                body={
                    "result": {
                        "running": state.applier_enabled,
                        "lastTick": state.last_tick,
                    }
                },
            )

        raise bad_request("unsupported replication path")


class WalHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort) -> None:
        self._storage = storage

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method == "GET" and request.path == "/_api/wal/properties":
            return HttpResponse(
                status_code=200,
                body={
                    "result": {
                        "files": self._storage.current_wal_files(),
                        "currentTick": self._storage.current_tick(),
                        "recoveryState": self._storage.recovery_state().value,
                    }
                },
            )

        if request.method == "PUT" and request.path == "/_api/wal/flush":
            return HttpResponse(status_code=200, body={"result": self._storage.flush_wal()})

        raise bad_request("unsupported wal path")


class JobHandler(RestHandler):
    def __init__(self, jobs: InMemoryJobManager) -> None:
        self._jobs = jobs

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and len(request.suffixes) == 0:
            payload = request.body if isinstance(request.body, dict) else {}
            job = self._jobs.create(payload=payload)
            return HttpResponse(status_code=202, body={"result": job})

        if request.method == "GET" and len(request.suffixes) == 0:
            return HttpResponse(status_code=200, body={"result": self._jobs.list_ids()})

        if request.method == "GET" and len(request.suffixes) == 1 and request.suffixes[0] in {
            "done",
            "pending",
        }:
            return HttpResponse(
                status_code=200,
                body={"result": self._jobs.list_ids(status=request.suffixes[0])},
            )

        if request.method == "GET" and len(request.suffixes) == 1:
            job = self._jobs.get(request.suffixes[0])
            if job is None:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"job '{request.suffixes[0]}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": job})

        if request.method == "DELETE" and len(request.suffixes) == 1:
            removed = self._jobs.delete(request.suffixes[0])
            if not removed:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"job '{request.suffixes[0]}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": {"id": request.suffixes[0], "deleted": True}})

        raise bad_request("unsupported job path")


class TasksHandler(RestHandler):
    def __init__(self, tasks: InMemoryTaskManager) -> None:
        self._tasks = tasks

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and len(request.suffixes) == 0:
            if not isinstance(request.body, dict):
                raise bad_request("task creation expects JSON object")
            task = self._tasks.create(request.body)
            return HttpResponse(status_code=201, body={"result": task})

        if request.method == "GET" and len(request.suffixes) == 0:
            return HttpResponse(status_code=200, body={"result": self._tasks.list()})

        if request.method == "GET" and len(request.suffixes) == 1:
            task = self._tasks.get(request.suffixes[0])
            if task is None:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"task '{request.suffixes[0]}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": task})

        if request.method == "DELETE" and len(request.suffixes) == 1:
            removed = self._tasks.delete(request.suffixes[0])
            if not removed:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"task '{request.suffixes[0]}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": {"id": request.suffixes[0], "deleted": True}})

        raise bad_request("unsupported tasks path")


class AdminClusterHandler(RestHandler):
    def __init__(self, cluster: ClusterService) -> None:
        self._cluster = cluster

    def handle(self, request: HttpRequest) -> HttpResponse:
        if not self._cluster.enabled:
            raise bad_request("cluster API not enabled")

        if request.method == "GET" and request.path == "/_admin/cluster/health":
            return HttpResponse(status_code=200, body={"result": self._cluster.health()})

        if request.method == "GET" and request.path == "/_admin/cluster/role":
            return HttpResponse(
                status_code=200,
                body={"result": {"role": self._cluster.role()}},
            )

        if request.method == "GET" and request.path == "/_admin/cluster/numberOfServers":
            return HttpResponse(
                status_code=200,
                body={"result": self._cluster.number_of_servers()},
            )

        if request.method == "GET" and request.path == "/_admin/cluster/endpoints":
            return HttpResponse(
                status_code=200,
                body={"result": self._cluster.topology()},
            )

        if request.method == "POST" and request.path == "/_admin/cluster/heartbeat":
            if not isinstance(request.body, dict):
                raise bad_request("cluster heartbeat expects JSON object")
            server_id = str(request.body.get("serverId", "")).strip()
            if not server_id:
                raise bad_request("cluster heartbeat requires serverId")
            status = str(request.body.get("status", "GOOD"))
            return HttpResponse(
                status_code=200,
                body={"result": self._cluster.record_heartbeat(server_id=server_id, status=status)},
            )

        if request.method == "GET" and request.path == "/_admin/cluster/shard-leadership":
            return HttpResponse(
                status_code=200,
                body={"result": self._cluster.shard_leadership()},
            )

        if request.method == "POST" and request.path == "/_admin/cluster/shard-leadership":
            if not isinstance(request.body, dict):
                raise bad_request("cluster shard leadership expects JSON object")
            shard = str(request.body.get("shard", "")).strip()
            leader = str(request.body.get("leader", "")).strip()
            force = bool(request.body.get("force", False))
            if not shard or not leader:
                raise bad_request("cluster shard leadership requires shard and leader")
            try:
                assigned = self._cluster.assign_shard_leader(shard=shard, leader=leader, force=force)
            except RuntimeError as exc:
                raise bad_request(str(exc)) from exc
            return HttpResponse(status_code=200, body={"result": assigned})

        if (
            request.method == "DELETE"
            and request.prefix == "/_admin/cluster"
            and len(request.suffixes) == 2
            and request.suffixes[0] == "shard-leadership"
        ):
            shard = request.suffixes[1]
            force = bool(request.body.get("force", False)) if isinstance(request.body, dict) else False
            try:
                removed = self._cluster.release_shard_leader(shard=shard, force=force)
            except RuntimeError as exc:
                raise bad_request(str(exc)) from exc
            if not removed:
                return HttpResponse(
                    status_code=404,
                    body={
                        "error": True,
                        "code": 404,
                        "errorNum": 404,
                        "errorMessage": f"shard leadership '{shard}' not found",
                    },
                )
            return HttpResponse(status_code=200, body={"result": {"shard": shard, "released": True}})

        if request.path == "/_admin/cluster/maintenance":
            if request.method == "GET":
                return HttpResponse(
                    status_code=200,
                    body={"result": {"enabled": self._cluster.maintenance()}},
                )
            if request.method in {"PUT", "POST"}:
                enabled = False
                if isinstance(request.body, dict):
                    enabled = bool(request.body.get("enabled", False))
                return HttpResponse(
                    status_code=200,
                    body={"result": {"enabled": self._cluster.set_maintenance(enabled)}},
                )

        if request.method == "DELETE" and request.path == "/_admin/cluster/maintenance":
            return HttpResponse(
                status_code=200,
                body={"result": {"enabled": self._cluster.set_maintenance(False)}},
            )

        raise bad_request("unsupported cluster path")


class DbPrefixedApiHandler(RestHandler):
    def __init__(self, storage: RocksDBEnginePort, manager: InMemoryTransactionManager) -> None:
        self._storage = storage
        self._manager = manager

    def handle(self, request: HttpRequest) -> HttpResponse:
        suffixes = request.suffixes
        if len(suffixes) < 3:
            raise bad_request("expected /_db/<database>/_api/<resource>")

        database = suffixes[0]
        if suffixes[1] != "_api":
            raise bad_request("expected /_db/<database>/_api/<resource>")

        resource = suffixes[2]
        delegated_path = "/_api/" + "/".join(suffixes[2:])
        delegated = HttpRequest(
            method=request.method,
            path=delegated_path,
            api_version=request.api_version,
            headers=request.headers,
            body=request.body,
            prefix="/_api/" + resource,
            suffixes=suffixes[3:],
        )
        delegated.headers["x-database"] = database

        if resource == "collection":
            return CollectionHandler(self._storage).handle(delegated)
        if resource == "document":
            return DocumentHandler(self._storage).handle(delegated)
        if resource == "edges":
            return EdgesHandler(self._storage).handle(delegated)
        if resource == "import":
            return ImportHandler(self._storage).handle(delegated)
        if resource == "index":
            return IndexHandler(self._storage).handle(delegated)
        if resource == "view":
            return ViewHandler(self._storage).handle(delegated)
        if resource == "transaction":
            return TransactionHandler(self._manager).handle(delegated)

        raise bad_request(f"unsupported db-prefixed resource '{resource}'")


def _resolve_database_from_path(request: HttpRequest) -> str:
    explicit = request.headers.get("x-database")
    if explicit:
        return explicit

    path = request.path
    if path.startswith("/_db/"):
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            return parts[1]
    return "_system"


@dataclass(slots=True)
class ServerRuntime:
    app_server: ApplicationServer
    handler_factory: RestHandlerFactory
    transaction_manager: InMemoryTransactionManager
    job_manager: InMemoryJobManager
    task_manager: InMemoryTaskManager
    storage_engine: RocksDBEnginePort
    auth: AuthService
    metrics: dict[str, object]
    replication: ReplicationService
    cluster: ClusterService
    logger: StructuredLogBuffer
    artifact_recorder: ValidationArtifactRecorder

    def handle_request(self, request: HttpRequest) -> HttpResponse:
        request_id = uuid4().hex
        started_ns = perf_counter_ns()
        principal = "anonymous"

        self._record_request()
        try:
            principal = self._enforce_auth(request)
            handler = self.handler_factory.create_handler(request)
            response = self.handler_factory.invoke(handler, request)
        except ApiError as exc:
            response = HttpResponse(status_code=exc.status_code, body=exc.to_payload())

        duration_ms = int((perf_counter_ns() - started_ns) / 1_000_000)
        self._record_response(request.path, response.status_code, duration_ms)
        self._record_observability(
            request_id=request_id,
            request=request,
            response=response,
            duration_ms=duration_ms,
            principal=principal,
        )
        return response

    def _record_request(self) -> None:
        self.metrics["requests_total"] = int(self.metrics["requests_total"]) + 1

    def _record_response(self, path: str, status_code: int, duration_ms: int) -> None:
        by_status = self.metrics["responses_by_status"]
        by_status[str(status_code)] = by_status.get(str(status_code), 0) + 1

        by_path = self.metrics["requests_by_path"]
        by_path[path] = by_path.get(path, 0) + 1

        latency = self.metrics["latency_by_path_ms"]
        entry = latency.get(path, {"count": 0, "totalMs": 0, "avgMs": 0})
        entry["count"] += 1
        entry["totalMs"] += duration_ms
        entry["avgMs"] = round(entry["totalMs"] / entry["count"], 2)
        latency[path] = entry

    def _record_observability(
        self,
        *,
        request_id: str,
        request: HttpRequest,
        response: HttpResponse,
        duration_ms: int,
        principal: str,
    ) -> None:
        self.logger.emit(
            "INFO",
            "http.request",
            "request handled",
            requestId=request_id,
            method=request.method,
            path=request.path,
            apiVersion=request.api_version,
            statusCode=response.status_code,
            durationMs=duration_ms,
            principal=principal,
        )

        self.artifact_recorder.record_request_result(
            request_id=request_id,
            method=request.method,
            path=request.path,
            api_version=request.api_version,
            status_code=response.status_code,
            duration_ms=duration_ms,
            principal=principal,
        )

    def _enforce_auth(self, request: HttpRequest) -> str:
        if request.path in {"/_api/version", "/_admin/version", "/_open/auth", "/_api/token"}:
            return "anonymous"

        header = request.headers.get("authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            raise unauthorized("missing bearer token")

        token = header[len(prefix) :]
        principal = self.auth.validate_token(token)
        if principal is None:
            raise unauthorized("invalid bearer token")

        request.headers["x-principal"] = principal
        if request.path.startswith("/_admin/") and not self.auth.is_admin(principal):
            raise forbidden("admin privileges required")
        return principal


def _handler_ctor(handler_type: type[RestHandler]):
    def _build(_data: dict | None = None) -> RestHandler:
        return handler_type()

    return _build


def _database_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return DatabaseHandler(storage)

    return _build


def _engine_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return EngineHandler(storage)

    return _build


def _transaction_handler_ctor(manager: InMemoryTransactionManager):
    def _build(_data: dict | None = None) -> RestHandler:
        return TransactionHandler(manager)

    return _build


def _open_auth_handler_ctor(auth: AuthService):
    def _build(_data: dict | None = None) -> RestHandler:
        return OpenAuthHandler(auth)

    return _build


def _token_handler_ctor(auth: AuthService):
    def _build(_data: dict | None = None) -> RestHandler:
        return TokenHandler(auth)

    return _build


def _user_handler_ctor(auth: AuthService):
    def _build(_data: dict | None = None) -> RestHandler:
        return UserHandler(auth)

    return _build


def _admin_status_handler_ctor(app_server: ApplicationServer):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminStatusHandler(app_server)

    return _build


def _admin_time_handler_ctor():
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminTimeHandler()

    return _build


def _admin_compact_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminCompactHandler(storage)

    return _build


def _admin_shutdown_handler_ctor(app_server: ApplicationServer):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminShutdownHandler(app_server)

    return _build


def _admin_metrics_handler_ctor(metrics: dict[str, object]):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminMetricsHandler(metrics)

    return _build


def _admin_log_handler_ctor(logger: StructuredLogBuffer):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminLogHandler(logger)

    return _build


def _admin_server_handler_ctor(
    app_server: ApplicationServer,
    storage: RocksDBEnginePort,
    cluster: ClusterService,
):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminServerHandler(app_server, storage, cluster)

    return _build


def _admin_server_id_handler_ctor(cluster: ClusterService):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminServerIdHandler(cluster)

    return _build


def _admin_statistics_handler_ctor(metrics: dict[str, object]):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminStatisticsHandler(metrics)

    return _build


def _admin_statistics_description_handler_ctor():
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminStatisticsDescriptionHandler()

    return _build


def _admin_options_handler_ctor():
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminOptionsHandler()

    return _build


def _admin_options_description_handler_ctor():
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminOptionsDescriptionHandler()

    return _build


def _admin_system_report_handler_ctor(
    app_server: ApplicationServer,
    metrics: dict[str, object],
    logger: StructuredLogBuffer,
    artifact_recorder: ValidationArtifactRecorder,
):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminSystemReportHandler(app_server, metrics, logger, artifact_recorder)

    return _build


def _admin_routing_reload_handler_ctor():
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminRoutingReloadHandler()

    return _build


def _replication_handler_ctor(replication: ReplicationService, storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return ReplicationHandler(replication, storage)

    return _build


def _wal_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return WalHandler(storage)

    return _build


def _job_handler_ctor(jobs: InMemoryJobManager):
    def _build(_data: dict | None = None) -> RestHandler:
        return JobHandler(jobs)

    return _build


def _tasks_handler_ctor(tasks: InMemoryTaskManager):
    def _build(_data: dict | None = None) -> RestHandler:
        return TasksHandler(tasks)

    return _build


def _admin_cluster_handler_ctor(cluster: ClusterService):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminClusterHandler(cluster)

    return _build


def _collection_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return CollectionHandler(storage)

    return _build


def _document_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return DocumentHandler(storage)

    return _build


def _edges_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return EdgesHandler(storage)

    return _build


def _import_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return ImportHandler(storage)

    return _build


def _index_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return IndexHandler(storage)

    return _build


def _view_handler_ctor(storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return ViewHandler(storage)

    return _build


def _db_prefixed_api_handler_ctor(storage: RocksDBEnginePort, manager: InMemoryTransactionManager):
    def _build(_data: dict | None = None) -> RestHandler:
        return DbPrefixedApiHandler(storage, manager)

    return _build


def _port_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_default_server(
    cluster_enabled: bool = True,
    artifact_dir: str | None = None,
    rocksdb_root: str | None = None,
) -> ServerRuntime:
    port_root = _port_root()
    default_rocksdb_root = port_root / "artifacts" / "rocksdb"
    default_validation_dir = port_root / "artifacts" / "validation" / "runtime"

    app_server = ApplicationServer()
    app_server.register_feature(Feature(name="Config"))
    app_server.register_feature(Feature(name="Network", depends_on={"Config"}))
    app_server.register_feature(Feature(name="Rest", depends_on={"Network"}))

    transaction_manager = InMemoryTransactionManager()
    job_manager = InMemoryJobManager()
    task_manager = InMemoryTaskManager()
    storage_engine = RocksDBEnginePort(
        RocksDBPortConfig.from_root(rocksdb_root or default_rocksdb_root)
    )
    auth = AuthService()
    auth.create_user("root", "deethoughtdb", is_admin=True)
    replication = ReplicationService(mode="cluster" if cluster_enabled else "single")
    cluster = ClusterService(role="coordinator" if cluster_enabled else "single", enabled=cluster_enabled)

    metrics: dict[str, object] = {
        "requests_total": 0,
        "responses_by_status": {},
        "requests_by_path": {},
        "latency_by_path_ms": {},
    }
    logger = StructuredLogBuffer()
    recorder = ValidationArtifactRecorder(
        base_dir=Path(artifact_dir) if artifact_dir else default_validation_dir
    )

    storage_engine.create_database("_system")

    handler_factory = RestHandlerFactory(max_api_version=2)
    handler_factory.add_handler("/_api/version", _handler_ctor(VersionHandler), [1, 2])
    handler_factory.add_prefix_handler("/_api/aql", _handler_ctor(AqlDisabledHandler), [1, 2])
    handler_factory.add_prefix_handler("/_api/query", _handler_ctor(AqlDisabledHandler), [1, 2])
    handler_factory.add_prefix_handler("/_api/cursor", _handler_ctor(AqlDisabledHandler), [1, 2])
    handler_factory.add_prefix_handler("/_api/explain", _handler_ctor(AqlDisabledHandler), [1, 2])
    handler_factory.add_handler("/_admin/version", _handler_ctor(VersionHandler), [1, 2])
    handler_factory.add_handler("/_admin/status", _admin_status_handler_ctor(app_server), [1, 2])
    handler_factory.add_handler("/_admin/time", _admin_time_handler_ctor(), [1, 2])
    handler_factory.add_handler("/_admin/compact", _admin_compact_handler_ctor(storage_engine), [1, 2])
    handler_factory.add_handler("/_admin/shutdown", _admin_shutdown_handler_ctor(app_server), [1, 2])
    handler_factory.add_handler("/_admin/log", _admin_log_handler_ctor(logger), [1, 2])
    handler_factory.add_handler(
        "/_admin/server",
        _admin_server_handler_ctor(app_server, storage_engine, cluster),
        [1, 2],
    )
    handler_factory.add_handler(
        "/_admin/server/id",
        _admin_server_id_handler_ctor(cluster),
        [1, 2],
    )
    handler_factory.add_handler(
        "/_admin/statistics",
        _admin_statistics_handler_ctor(metrics),
        [1, 2],
    )
    handler_factory.add_handler(
        "/_admin/statistics-description",
        _admin_statistics_description_handler_ctor(),
        [1, 2],
    )
    handler_factory.add_handler("/_admin/options", _admin_options_handler_ctor(), [1, 2])
    handler_factory.add_handler(
        "/_admin/options-description",
        _admin_options_description_handler_ctor(),
        [1, 2],
    )
    handler_factory.add_prefix_handler("/_admin/metrics", _admin_metrics_handler_ctor(metrics), [1, 2])
    handler_factory.add_handler(
        "/_admin/system-report",
        _admin_system_report_handler_ctor(app_server, metrics, logger, recorder),
        [1, 2],
    )
    handler_factory.add_handler(
        "/_admin/routing/reload",
        _admin_routing_reload_handler_ctor(),
        [1, 2],
    )
    handler_factory.add_prefix_handler("/_admin/cluster", _admin_cluster_handler_ctor(cluster), [1, 2])
    handler_factory.add_handler("/_open/auth", _open_auth_handler_ctor(auth), [1, 2])
    handler_factory.add_handler("/_api/token", _token_handler_ctor(auth), [1, 2])
    handler_factory.add_prefix_handler("/_api/user", _user_handler_ctor(auth), [1, 2])
    handler_factory.add_prefix_handler(
        "/_api/database", _database_handler_ctor(storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler("/_api/engine", _engine_handler_ctor(storage_engine), [1, 2])
    handler_factory.add_prefix_handler(
        "/_api/collection", _collection_handler_ctor(storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/document", _document_handler_ctor(storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/edges", _edges_handler_ctor(storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/import", _import_handler_ctor(storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/index", _index_handler_ctor(storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/view", _view_handler_ctor(storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/transaction", _transaction_handler_ctor(transaction_manager), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/replication", _replication_handler_ctor(replication, storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/wal", _wal_handler_ctor(storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler("/_api/job", _job_handler_ctor(job_manager), [1, 2])
    handler_factory.add_prefix_handler("/_api/tasks", _tasks_handler_ctor(task_manager), [1, 2])
    handler_factory.add_prefix_handler(
        "/_db", _db_prefixed_api_handler_ctor(storage_engine, transaction_manager), [1, 2]
    )
    handler_factory.add_prefix_handler("/", _handler_ctor(CatchAllHandler), [1, 2])
    handler_factory.seal()

    app_server.boot()

    return ServerRuntime(
        app_server=app_server,
        handler_factory=handler_factory,
        transaction_manager=transaction_manager,
        job_manager=job_manager,
        task_manager=task_manager,
        storage_engine=storage_engine,
        auth=auth,
        metrics=metrics,
        replication=replication,
        cluster=cluster,
        logger=logger,
        artifact_recorder=recorder,
    )
