from __future__ import annotations

import secrets


class AuthService:
    def __init__(self) -> None:
        self._users: dict[str, dict[str, object]] = {}
        self._tokens: dict[str, str] = {}

    def create_user(self, username: str, password: str, is_admin: bool = False) -> None:
        self._users[username] = {"password": password, "is_admin": is_admin}

    def authenticate(self, username: str, password: str) -> str | None:
        record = self._users.get(username)
        if record is None:
            return None
        if record["password"] != password:
            return None
        token = secrets.token_hex(16)
        self._tokens[token] = username
        return token

    def validate_token(self, token: str) -> str | None:
        return self._tokens.get(token)

    def is_admin(self, username: str) -> bool:
        user = self._users.get(username)
        if user is None:
            return False
        return bool(user["is_admin"])
