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
        self._server_id = "2001001" if mode == "cluster" else "1001001"
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

    def start_applier(self) -> ReplicationState:
        self._state.applier_enabled = True
        self._state.last_tick += 1
        return self._state

    def stop_applier(self) -> ReplicationState:
        self._state.applier_enabled = False
        self._state.last_tick += 1
        return self._state

    def clear_applier_config(self) -> None:
        self._applier_config = {
            "endpoint": "",
            "username": "",
            "includeSystem": True,
        }
        self._state.applier_enabled = False
        self._state.last_tick += 1

    def server_id(self) -> str:
        return self._server_id

    def applier_state(self) -> dict[str, object]:
        return {
            "running": self._state.applier_enabled,
            "lastAppliedContinuousTick": self._state.last_tick,
            "lastProcessedContinuousTick": self._state.last_tick,
            "safeResumeTick": self._state.last_tick,
            "serverId": self._server_id,
        }

    def sync(self) -> dict[str, object]:
        self._state.last_tick += 1
        return {
            "lastLogTick": self._state.last_tick,
            "barrierId": self._state.last_tick,
            "serverId": self._server_id,
        }


class ClusterService:
    def __init__(self, role: str = "single", enabled: bool = False) -> None:
        self._enabled = enabled
        self._role = role
        self._maintenance = False
        self._servers: dict[str, str] = {
            "PRMR-1": "GOOD",
            "CRDN-1": "GOOD",
        }
        self._heartbeat_seq = 0

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
            "maintenance": self._maintenance,
        }

    def set_maintenance(self, enabled: bool) -> bool:
        self._maintenance = enabled
        return self._maintenance

    def maintenance(self) -> bool:
        return self._maintenance

    def number_of_servers(self) -> dict[str, int]:
        coordinators = sum(1 for server in self._servers if server.startswith("CRDN"))
        dbservers = sum(1 for server in self._servers if server.startswith("PRMR"))
        return {
            "coordinators": coordinators,
            "dbservers": dbservers,
            "total": len(self._servers),
        }

    def topology(self) -> dict[str, object]:
        coordinators = sorted(server for server in self._servers if server.startswith("CRDN"))
        dbservers = sorted(server for server in self._servers if server.startswith("PRMR"))
        return {
            "coordinators": coordinators,
            "dbservers": dbservers,
            "statuses": dict(self._servers),
        }

    def record_heartbeat(self, server_id: str, status: str = "GOOD") -> dict[str, object]:
        self._heartbeat_seq += 1
        self._servers[server_id] = status
        return {
            "serverId": server_id,
            "status": status,
            "heartbeatSeq": self._heartbeat_seq,
        }
