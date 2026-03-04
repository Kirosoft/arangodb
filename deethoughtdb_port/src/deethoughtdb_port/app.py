from __future__ import annotations

from dataclasses import dataclass

from deethoughtdb_port.api.errors import bad_request
from deethoughtdb_port.domain.inmemory import (
    InMemoryCatalogService,
    InMemoryTransactionManager,
    NoopStorageEngine,
)
from deethoughtdb_port.runtime.feature import Feature
from deethoughtdb_port.runtime.server import ApplicationServer
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


@dataclass(slots=True)
class ServerRuntime:
    app_server: ApplicationServer
    handler_factory: RestHandlerFactory
    catalog: InMemoryCatalogService
    transaction_manager: InMemoryTransactionManager
    storage_engine: NoopStorageEngine


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


def build_default_server() -> ServerRuntime:
    app_server = ApplicationServer()
    app_server.register_feature(Feature(name="Config"))
    app_server.register_feature(Feature(name="Network", depends_on={"Config"}))
    app_server.register_feature(Feature(name="Rest", depends_on={"Network"}))

    catalog = InMemoryCatalogService()
    transaction_manager = InMemoryTransactionManager()
    storage_engine = NoopStorageEngine()

    catalog.create_database("_system")

    handler_factory = RestHandlerFactory(max_api_version=2)
    handler_factory.add_handler("/_api/version", _handler_ctor(VersionHandler), [1, 2])
    handler_factory.add_handler("/_admin/version", _handler_ctor(VersionHandler), [1, 2])
    handler_factory.add_prefix_handler(
        "/_api/database", _database_handler_ctor(catalog), [1, 2]
    )
    handler_factory.add_prefix_handler(
        "/_api/transaction", _transaction_handler_ctor(transaction_manager), [1, 2]
    )
    handler_factory.add_prefix_handler("/", _handler_ctor(CatchAllHandler), [1, 2])
    handler_factory.seal()

    return ServerRuntime(
        app_server=app_server,
        handler_factory=handler_factory,
        catalog=catalog,
        transaction_manager=transaction_manager,
        storage_engine=storage_engine,
    )
