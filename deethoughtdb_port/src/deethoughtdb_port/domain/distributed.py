from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ReplicationState:
    mode: str
    applier_enabled: bool
    last_tick: int


class ReplicationService:
    def __init__(self, mode: str = "single") -> None:
        self._state = ReplicationState(mode=mode, applier_enabled=False, last_tick=0)
        self._applier_config: dict[str, object] = {
            "endpoint": "",
            "username": "",
            "includeSystem": True,
        }

    def state(self) -> ReplicationState:
        return self._state

    def applier_config(self) -> dict[str, object]:
        return dict(self._applier_config)

    def update_applier_config(self, updates: dict[str, object]) -> dict[str, object]:
        self._applier_config.update(updates)
        self._state.applier_enabled = bool(self._applier_config.get("endpoint"))
        self._state.last_tick += 1
        return self.applier_config()


class ClusterService:
    def __init__(self, role: str = "single", enabled: bool = False) -> None:
        self._enabled = enabled
        self._role = role
        self._servers: dict[str, str] = {
            "PRMR-1": "GOOD",
            "CRDN-1": "GOOD",
        }

    @property
    def enabled(self) -> bool:
        return self._enabled

    def role(self) -> str:
        return self._role

    def health(self) -> dict[str, object]:
        return {
            "role": self._role,
            "enabled": self._enabled,
            "servers": dict(self._servers),
        }
