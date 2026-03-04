from __future__ import annotations

from collections.abc import Callable

from deethoughtdb_port.api.errors import ApiError, not_found, unknown_api_version

from .http_models import HttpRequest, HttpResponse
from .rest_handler import RestHandler

HandlerFactory = Callable[[dict | None], RestHandler]


class RestHandlerFactory:
    def __init__(self, max_api_version: int = 2) -> None:
        size = max_api_version + 1
        self._constructors: list[dict[str, tuple[HandlerFactory, dict | None]]] = [
            {} for _ in range(size)
        ]
        self._prefixes: list[list[str]] = [[] for _ in range(size)]
        self._sealed = False

    def add_handler(
        self,
        path: str,
        constructor: HandlerFactory,
        api_versions: list[int],
        data: dict | None = None,
    ) -> None:
        self._ensure_mutable()
        for api_version in api_versions:
            mapping = self._constructors[api_version]
            if path in mapping:
                raise ValueError(
                    f"duplicate path handler '{path}' for API version {api_version}"
                )
            mapping[path] = (constructor, data)

    def add_prefix_handler(
        self,
        path: str,
        constructor: HandlerFactory,
        api_versions: list[int],
        data: dict | None = None,
    ) -> None:
        self.add_handler(path, constructor, api_versions, data)
        for api_version in api_versions:
            self._prefixes[api_version].append(path)

    def seal(self) -> None:
        self._ensure_mutable()
        for prefixes in self._prefixes:
            prefixes.sort(key=len, reverse=True)
        self._sealed = True

    def create_handler(self, request: HttpRequest) -> RestHandler:
        self._ensure_sealed()

        if request.api_version >= len(self._constructors):
            raise unknown_api_version(request.api_version, request.path)

        constructors = self._constructors[request.api_version]
        direct = constructors.get(request.path)
        if direct is not None:
            ctor, data = direct
            request.prefix = request.path
            return ctor(data)

        path = request.path
        prefixes = self._prefixes[request.api_version]
        prefix_match = None
        for prefix in prefixes:
            if len(prefix) >= len(path):
                continue
            if path.startswith(prefix) and path[len(prefix)] == "/":
                prefix_match = prefix
                break

        if prefix_match is None:
            catch_all = constructors.get("/")
            if catch_all is None:
                raise not_found(request.path)
            ctor, data = catch_all
            request.prefix = "/"
            request.suffixes = [s for s in path.split("/") if s]
            return ctor(data)

        ctor, data = constructors[prefix_match]
        request.prefix = prefix_match

        suffix = path[len(prefix_match) + 1 :]
        request.suffixes = [part for part in suffix.split("/") if part]
        return ctor(data)

    @staticmethod
    def invoke(handler: RestHandler, request: HttpRequest) -> HttpResponse:
        try:
            return handler.handle(request)
        except ApiError as exc:
            return HttpResponse(status_code=exc.status_code, body=exc.to_payload())

    def _ensure_mutable(self) -> None:
        if self._sealed:
            raise RuntimeError("handler factory already sealed")

    def _ensure_sealed(self) -> None:
        if not self._sealed:
            raise RuntimeError("handler factory must be sealed before use")
