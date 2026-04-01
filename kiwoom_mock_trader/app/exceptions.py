"""Application specific exceptions."""


class KiwoomError(Exception):
    """Base exception for the project."""


class KiwoomConfigurationError(KiwoomError):
    """Raised when local configuration is invalid."""


class KiwoomAuthError(KiwoomError):
    """Raised when token issuance or token usage fails."""


class KiwoomAPIError(KiwoomError):
    """Raised when Kiwoom REST API returns an error."""


class KiwoomSafetyError(KiwoomError):
    """Raised when a safety guard blocks execution."""


class KiwoomRiskError(KiwoomError):
    """Raised when risk management halts trading."""

