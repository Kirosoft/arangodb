from __future__ import annotations

import secrets
import time


class AuthService:
    def __init__(self) -> None:
        self._users: dict[str, dict[str, object]] = {}
        self._tokens: dict[str, dict[str, object]] = {}
        self._reload_version = 0

    def create_user(self, username: str, password: str, is_admin: bool = False) -> None:
        self._users[username] = {"password": password, "is_admin": is_admin}

    def list_users(self) -> list[dict[str, object]]:
        return [
            {"user": username, "active": True, "extra": {}, "isAdmin": bool(record["is_admin"]) }
            for username, record in sorted(self._users.items(), key=lambda item: item[0])
        ]

    def remove_user(self, username: str) -> bool:
        removed = self._users.pop(username, None)
        if removed is None:
            return False
        self._tokens = {
            token: info
            for token, info in self._tokens.items()
            if str(info.get("user")) != username
        }
        return True

    def authenticate(self, username: str, password: str, ttl_seconds: int | None = None) -> str | None:
        record = self._users.get(username)
        if record is None:
            return None
        if record["password"] != password:
            return None
        token = secrets.token_hex(16)
        expires_at: float | None = None
        if ttl_seconds is not None:
            expires_at = time.time() + max(0, ttl_seconds)
        self._tokens[token] = {"user": username, "expiresAt": expires_at}
        return token

    def validate_token(self, token: str) -> str | None:
        info = self._tokens.get(token)
        if info is None:
            return None
        expires_at = info.get("expiresAt")
        if isinstance(expires_at, (int, float)) and time.time() >= float(expires_at):
            self._tokens.pop(token, None)
            return None
        user = info.get("user")
        if not isinstance(user, str):
            return None
        return user

    def is_admin(self, username: str) -> bool:
        user = self._users.get(username)
        if user is None:
            return False
        return bool(user["is_admin"])

    def reload_permissions(self) -> int:
        self._reload_version += 1
        return self._reload_version
