from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FeatureState(str, Enum):
    NEW = "new"
    PREPARED = "prepared"
    STARTED = "started"
    STOPPED = "stopped"


@dataclass(slots=True)
class Feature:
    name: str
    depends_on: set[str] = field(default_factory=set)
    state: FeatureState = FeatureState.NEW

    def collect_options(self, _config_registry: dict) -> None:
        return None

    def validate_options(self, _config: dict) -> None:
        return None

    def prepare(self, _runtime_context: dict) -> None:
        self.state = FeatureState.PREPARED

    def start(self) -> None:
        self.state = FeatureState.STARTED

    def begin_shutdown(self) -> None:
        return None

    def stop(self) -> None:
        self.state = FeatureState.STOPPED
