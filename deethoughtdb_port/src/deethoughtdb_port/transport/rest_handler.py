from __future__ import annotations

from abc import ABC, abstractmethod

from .http_models import HttpRequest, HttpResponse


class RestHandler(ABC):
    @abstractmethod
    def handle(self, request: HttpRequest) -> HttpResponse:
        raise NotImplementedError
