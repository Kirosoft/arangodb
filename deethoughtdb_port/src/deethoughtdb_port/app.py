from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4

from deethoughtdb_port.api.errors import ApiError, bad_request, forbidden, unauthorized
from deethoughtdb_port.domain.auth import AuthService
from deethoughtdb_port.domain.inmemory import (
    InMemoryCatalogService,
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
        return HttpResponse(
            status_code=200,
            body={
                "server": "deethoughtdb",
                "apiVersion": request.api_version,
                "path": request.path,
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
    def __init__(self, catalog: InMemoryCatalogService) -> None:
        self._catalog = catalog

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method == "GET":
            databases = [
                {"id": database.database_id, "name": database.name}
                for database in self._catalog.list_databases()
            ]
            return HttpResponse(status_code=200, body={"result": databases})

        if request.method == "POST":
            if not isinstance(request.body, dict) or "name" not in request.body:
                raise bad_request("database creation expects body {'name': '<db-name>'}")
            database = self._catalog.create_database(str(request.body["name"]))
            return HttpResponse(
                status_code=201,
                body={"result": {"id": database.database_id, "name": database.name}},
            )

        raise bad_request(f"unsupported method '{request.method}' for /_api/database")


class TransactionHandler(RestHandler):
    def __init__(self, manager: InMemoryTransactionManager) -> None:
        self._manager = manager

    def handle(self, request: HttpRequest) -> HttpResponse:
        if request.method != "POST":
            raise bad_request("transaction API expects POST")

        if request.path == "/_api/transaction/begin":
            transaction_id = self._manager.begin()
            return HttpResponse(status_code=201, body={"result": {"id": transaction_id}})

        if (
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
        if not username or not password:
            raise bad_request("/_open/auth requires username and password")

        token = self._auth.authenticate(username, password)
        if token is None:
            raise unauthorized("invalid credentials")
        return HttpResponse(status_code=200, body={"result": {"token": token}})


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

        raise bad_request("unsupported replication path")


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

        raise bad_request("unsupported cluster path")


@dataclass(slots=True)
class ServerRuntime:
    app_server: ApplicationServer
    handler_factory: RestHandlerFactory
    catalog: InMemoryCatalogService
    transaction_manager: InMemoryTransactionManager
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
        if request.path in {"/_api/version", "/_admin/version", "/_open/auth"}:
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


def _database_handler_ctor(catalog: InMemoryCatalogService):
    def _build(_data: dict | None = None) -> RestHandler:
        return DatabaseHandler(catalog)

    return _build


def _transaction_handler_ctor(manager: InMemoryTransactionManager):
    def _build(_data: dict | None = None) -> RestHandler:
        return TransactionHandler(manager)

    return _build


def _open_auth_handler_ctor(auth: AuthService):
    def _build(_data: dict | None = None) -> RestHandler:
        return OpenAuthHandler(auth)

    return _build


def _admin_status_handler_ctor(app_server: ApplicationServer):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminStatusHandler(app_server)

    return _build


def _admin_metrics_handler_ctor(metrics: dict[str, object]):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminMetricsHandler(metrics)

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


def _replication_handler_ctor(replication: ReplicationService, storage: RocksDBEnginePort):
    def _build(_data: dict | None = None) -> RestHandler:
        return ReplicationHandler(replication, storage)

    return _build


def _admin_cluster_handler_ctor(cluster: ClusterService):
    def _build(_data: dict | None = None) -> RestHandler:
        return AdminClusterHandler(cluster)

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

    catalog = InMemoryCatalogService()
    transaction_manager = InMemoryTransactionManager()
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

    catalog.create_database("_system")

    handler_factory = RestHandlerFactory(max_api_version=2)
    handler_factory.add_handler("/_api/version", _handler_ctor(VersionHandler), [1, 2])
    handler_factory.add_handler("/_admin/version", _handler_ctor(VersionHandler), [1, 2])
    handler_factory.add_handler("/_admin/status", _admin_status_handler_ctor(app_server), [1, 2])
    handler_factory.add_prefix_handler("/_admin/metrics", _admin_metrics_handler_ctor(metrics), [1, 2])
    handler_factory.add_handler(
        "/_admin/system-report",
        _admin_system_report_handler_ctor(app_server, metrics, logger, recorder),
        [1, 2],
    )
    handler_factory.add_prefix_handler("/_admin/cluster", _admin_cluster_handler_ctor(cluster), [1, 2])
    handler_factory.add_handler("/_open/auth", _open_auth_handler_ctor(auth), [1, 2])
    handler_factory.add_prefix_handler(
        "/_api/database", _database_handler_ctor(catalog), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/transaction", _transaction_handler_ctor(transaction_manager), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/replication", _replication_handler_ctor(replication, storage_engine), [1, 2]
    )
    handler_factory.add_prefix_handler("/", _handler_ctor(CatchAllHandler), [1, 2])
    handler_factory.seal()

    app_server.boot()

    return ServerRuntime(
        app_server=app_server,
        handler_factory=handler_factory,
        catalog=catalog,
        transaction_manager=transaction_manager,
        storage_engine=storage_engine,
        auth=auth,
        metrics=metrics,
        replication=replication,
        cluster=cluster,
        logger=logger,
        artifact_recorder=recorder,
    )
