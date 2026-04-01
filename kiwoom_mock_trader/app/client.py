"""Low level REST client for Kiwoom endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.auth import TokenManager
from app.exceptions import KiwoomAPIError, KiwoomAuthError
from app.models import AppSettings


@dataclass
class KiwoomResponse:
    """Normalized response wrapper."""

    body: dict[str, Any]
    headers: dict[str, str]
    cont_yn: bool
    next_key: str | None


class KiwoomRESTClient:
    """Synchronous HTTP client used by all services."""

    def __init__(
        self,
        settings: AppSettings,
        token_manager: TokenManager,
        logger: logging.Logger,
    ) -> None:
        self.settings = settings
        self.token_manager = token_manager
        self.logger = logger.getChild("client")
        self._http = httpx.Client(timeout=settings.api.request_timeout_seconds)

    def post(
        self,
        *,
        path: str,
        api_id: str,
        body: dict[str, Any] | None = None,
        continuation_key: str | None = None,
        retry_on_auth_error: bool = True,
    ) -> KiwoomResponse:
        """POST to a Kiwoom REST endpoint with OAuth headers."""

        token = self.token_manager.get_access_token(force_refresh=False)
        headers: dict[str, str] = {
            "Content-Type": "application/json;charset=UTF-8",
            "authorization": f"Bearer {token.token}",
            "api-id": api_id,
        }
        if continuation_key:
            headers["cont-yn"] = "Y"
            headers["next-key"] = continuation_key

        url = f"{self.settings.rest_base_url}{path}"
        try:
            response = self._http.post(url, headers=headers, json=body or {})
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401 and retry_on_auth_error:
                self.logger.warning("Received 401. Refreshing token and retrying once.")
                self.token_manager.get_access_token(force_refresh=True)
                return self.post(
                    path=path,
                    api_id=api_id,
                    body=body,
                    continuation_key=continuation_key,
                    retry_on_auth_error=False,
                )
            if exc.response.status_code == 401:
                raise KiwoomAuthError("Authorization failed while calling Kiwoom REST API.") from exc
            raise KiwoomAPIError(
                f"HTTP error from Kiwoom REST API for {api_id}: status={exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise KiwoomAPIError(f"HTTP request failed for api-id {api_id}.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise KiwoomAPIError(f"Response was not valid JSON for api-id {api_id}.") from exc

        return_code = payload.get("return_code")
        if return_code is not None and str(return_code) != "0":
            raise KiwoomAPIError(
                f"Kiwoom API error for {api_id}: {payload.get('return_msg', 'unknown error')}"
            )

        return KiwoomResponse(
            body=payload,
            headers=dict(response.headers),
            cont_yn=response.headers.get("cont-yn", "N").upper() == "Y",
            next_key=response.headers.get("next-key"),
        )
