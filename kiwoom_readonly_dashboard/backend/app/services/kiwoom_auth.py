"""Kiwoom OAuth token service."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.core.config import Settings


SEOUL_TZ = timezone(timedelta(hours=9), name="Asia/Seoul")


class KiwoomAuthError(RuntimeError):
    """Raised when Kiwoom authentication fails."""


@dataclass
class AccessToken:
    token: str
    token_type: str
    expires_at: datetime


class KiwoomAuthService:
    """Issue and cache Kiwoom OAuth tokens."""

    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger.getChild("kiwoom_auth")
        self.last_error: str | None = None
        self.last_updated_at: datetime | None = None
        self._cached_token: AccessToken | None = None
        self._recent_errors: list[str] = []

    async def get_token(self, force_refresh: bool = False) -> str:
        """Return a valid bearer token."""

        if not force_refresh:
            cached = self._load_cached_token()
            if cached and cached.expires_at > datetime.now(SEOUL_TZ) + timedelta(minutes=5):
                self._cached_token = cached
                return cached.token

        token = await self._request_new_token()
        self._save_token(token)
        self._cached_token = token
        self.last_updated_at = datetime.now(SEOUL_TZ)
        self.last_error = None
        return token.token

    async def _request_new_token(self) -> AccessToken:
        """Call Kiwoom OAuth token endpoint."""

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.settings.kiwoom_app_key,
            "secretkey": self.settings.kiwoom_secret_key,
        }
        url = f"{self.settings.kiwoom_rest_base_url}/oauth2/token"
        async with httpx.AsyncClient(timeout=self.settings.kiwoom_timeout_seconds) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                self.last_error = f"Token request failed: {exc}"
                self._remember_error(self.last_error)
                raise KiwoomAuthError(self.last_error) from exc
            except ValueError as exc:
                self.last_error = "Token response was not valid JSON."
                self._remember_error(self.last_error)
                raise KiwoomAuthError(self.last_error) from exc

        if str(data.get("return_code", "0")) not in {"0", "None", "null"}:
            self.last_error = data.get("return_msg", "unknown Kiwoom auth error")
            self._remember_error(self.last_error)
            raise KiwoomAuthError(self.last_error)

        expires_at = datetime.strptime(data["expires_dt"], "%Y%m%d%H%M%S").replace(tzinfo=SEOUL_TZ)
        self.logger.info("Issued a new Kiwoom access token.")
        return AccessToken(
            token=data["token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
        )

    def _load_cached_token(self) -> AccessToken | None:
        """Read token from memory or disk."""

        if self._cached_token and self._cached_token.expires_at > datetime.now(SEOUL_TZ):
            return self._cached_token

        path = Path(self.settings.token_cache_file)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return AccessToken(
                token=payload["token"],
                token_type=payload.get("token_type", "Bearer"),
                expires_at=datetime.fromisoformat(payload["expires_at"]),
            )
        except Exception as exc:  # pragma: no cover - defensive corruption handling.
            self.logger.warning("Ignoring invalid token cache: %s", exc)
            return None

    def _save_token(self, token: AccessToken) -> None:
        """Persist a token to disk."""

        path = Path(self.settings.token_cache_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "token": token.token,
                    "token_type": token.token_type,
                    "expires_at": token.expires_at.isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def get_recent_errors(self) -> list[str]:
        """Return recent auth errors for the status panel."""

        return list(self._recent_errors)

    def _remember_error(self, message: str) -> None:
        self._recent_errors.append(message)
        self._recent_errors = self._recent_errors[-10:]
