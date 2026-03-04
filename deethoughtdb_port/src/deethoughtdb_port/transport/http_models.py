from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HttpRequest:
    method: str
    path: str
    api_version: int = 1
    headers: dict[str, str] = field(default_factory=dict)
    body: dict | list | str | None = None
    prefix: str = ""
    suffixes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class HttpResponse:
    status_code: int
    body: dict
    headers: dict[str, str] = field(default_factory=dict)
