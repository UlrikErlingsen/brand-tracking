"""User-facing errors raised by Track Signal."""

from __future__ import annotations


class DataProblem(ValueError):
    """Raised when an analysis contract cannot be honored with the supplied data."""


def friendly_message(exc: Exception) -> str:
    """Return a useful message without exposing an internal traceback by default."""
    if isinstance(exc, DataProblem):
        return str(exc)
    if isinstance(exc, ValueError):
        return f"Track Signal could not complete that step: {exc}"
    return (
        "Track Signal could not complete that step. Check the data contract and try again. "
        "Set TRACKSIGNAL_DEBUG=1 before launch if you need technical details."
    )
