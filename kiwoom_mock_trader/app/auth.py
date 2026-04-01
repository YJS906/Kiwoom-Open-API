"""OAuth token issuance and caching."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from app.exceptions import KiwoomAuthError
from app.models import AccessToken, AppSettings
from app.utils import get_timezone, load_json_file, resolve_path, save_json_file


class TokenManager:
    """Manage Kiwoom REST OAuth tokens with local caching."""

    TOKEN_PATH = "/oauth2/token"
    REVOKE_PATH = "/oauth2/revoke"

    def __init__(self, settings: AppSettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger.getChild("auth")
        self.cache_path = resolve_path(settings.project_root, settings.runtime.token_cache_file)
        self._http = httpx.Client(timeout=settings.api.request_timeout_seconds)

    def get_access_token(self, force_refresh: bool = False) -> AccessToken:
        """Return a valid access token, issuing a new one when needed."""

        cached = self._load_cached_token()
        if not force_refresh and cached and not self._is_expired(cached):
            return cached

        fresh = self._request_new_token()
        self._save_token(fresh)
        return fresh

    def revoke_cached_token(self) -> None:
        """Revoke the locally cached token if one exists."""

        cached = self._load_cached_token()
        if not cached:
            self.logger.info("No cached token to revoke.")
            return

        payload = {
            "appkey": self.settings.credentials.app_key,
            "secretkey": self.settings.credentials.secret_key,
            "token": cached.token,
        }
        url = f"{self.settings.rest_base_url}{self.REVOKE_PATH}"
        try:
            response = self._http.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise KiwoomAuthError("Failed to revoke access token.") from exc

        if self.cache_path.exists():
            self.cache_path.unlink()
        self.logger.info("Cached token was revoked and removed from disk.")

    def _request_new_token(self) -> AccessToken:
        """Call Kiwoom OAuth token issuance endpoint."""

        payload = {
            "grant_type": "client_credentials",
            "appkey": self.settings.credentials.app_key,
            "secretkey": self.settings.credentials.secret_key,
        }
        url = f"{self.settings.rest_base_url}{self.TOKEN_PATH}"
        try:
            response = self._http.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise KiwoomAuthError("Failed to request a new access token.") from exc
        except ValueError as exc:
            raise KiwoomAuthError("Token response was not valid JSON.") from exc

        if str(data.get("return_code", "0")) not in {"0", "None", "null"}:
            raise KiwoomAuthError(
                f"Token issuance failed: {data.get('return_msg', 'unknown error')}"
            )

        token = AccessToken(
            token=data["token"],
            token_type=data.get("token_type", "bearer"),
            expires_dt=data["expires_dt"],
        )
        self.logger.info("Issued a new Kiwoom access token.")
        return token

    def _load_cached_token(self) -> AccessToken | None:
        """Load token cache if present."""

        payload = load_json_file(self.cache_path)
        if not payload:
            return None
        try:
            return AccessToken(**payload)
        except Exception as exc:  # pragma: no cover - defensive corruption handling.
            self.logger.warning("Ignoring invalid token cache: %s", exc)
            return None

    def _save_token(self, token: AccessToken) -> None:
        """Persist the issued token to disk."""

        save_json_file(self.cache_path, token.model_dump())

    def _is_expired(self, token: AccessToken) -> bool:
        """Treat tokens expiring within 5 minutes as expired."""

        timezone = get_timezone("Asia/Seoul")
        expires_at = datetime.strptime(token.expires_dt, "%Y%m%d%H%M%S").replace(tzinfo=timezone)
        return expires_at <= datetime.now(timezone) + timedelta(minutes=5)
