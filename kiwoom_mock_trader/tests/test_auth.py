"""Unit tests for token caching."""

from __future__ import annotations

from app.auth import TokenManager
from app.models import AccessToken


class StubTokenManager(TokenManager):
    """TokenManager that avoids real HTTP calls."""

    def __init__(self, settings, logger) -> None:
        super().__init__(settings, logger)
        self.issue_calls = 0

    def _request_new_token(self) -> AccessToken:
        self.issue_calls += 1
        return AccessToken(
            token=f"token-{self.issue_calls}",
            token_type="bearer",
            expires_dt="20991231235959",
        )


def test_get_access_token_uses_cache(settings, logger) -> None:
    """The second call should reuse the first cached token."""

    manager = StubTokenManager(settings, logger)

    first = manager.get_access_token()
    second = manager.get_access_token()

    assert first.token == "token-1"
    assert second.token == "token-1"
    assert manager.issue_calls == 1


def test_get_access_token_refreshes_expired_cache(settings, logger) -> None:
    """Expired cache files should trigger a refresh."""

    manager = StubTokenManager(settings, logger)
    manager._save_token(
        AccessToken(token="expired", token_type="bearer", expires_dt="20000101000000")
    )

    fresh = manager.get_access_token()

    assert fresh.token == "token-1"
    assert manager.issue_calls == 1

