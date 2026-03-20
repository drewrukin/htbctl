"""HTBctl exceptions."""


class HTBError(Exception):
    """Base exception for HTB API errors."""


class HTBAuthError(HTBError):
    """Invalid or expired token."""


class HTBMachineNotFoundError(HTBError):
    """Machine not found."""


class HTBSpawnError(HTBError):
    """Machine spawn error."""


class HTBRateLimitError(HTBError):
    """API rate limit exceeded (HTTP 429)."""
