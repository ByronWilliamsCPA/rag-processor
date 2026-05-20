"""Time utilities for RAG Processor.

Provides standardized datetime helpers compatible with Python 3.10+.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Alias `UTC = timezone.utc` because `datetime.UTC` was added in Python 3.11
# and this project's `requires-python = ">=3.10"` still supports 3.10. The
# UP017 ruff rule asks for `from datetime import UTC`, which would break the
# 3.10 leg of the python-compatibility matrix. Drop this alias (and the
# `# noqa: UP017` annotations across the codebase) when the project minimum
# moves to Python 3.11.
UTC = timezone.utc  # noqa: UP017


def utc_now() -> datetime:
    """Get current UTC datetime.

    Returns:
        Current UTC datetime with timezone info.

    Example:
        >>> now = utc_now()
        >>> now.tzinfo == UTC
        True
    """
    return datetime.now(tz=UTC)


def from_timestamp(timestamp: float | int) -> datetime:
    """Create UTC datetime from Unix timestamp.

    Args:
        timestamp: Unix timestamp (seconds since epoch).

    Returns:
        UTC datetime with timezone info.

    Example:
        >>> dt = from_timestamp(1640995200)  # 2022-01-01 00:00:00 UTC
        >>> dt.year == 2022
        True
    """
    return datetime.fromtimestamp(timestamp, tz=UTC)


def parse_iso_datetime(iso_string: str) -> datetime:
    """Parse ISO format datetime string to UTC datetime.

    Handles both 'Z' suffix and '+00:00' formats.

    Args:
        iso_string: ISO format datetime string.

    Returns:
        UTC datetime with timezone info.

    Example:
        >>> dt = parse_iso_datetime("2024-01-01T12:00:00Z")
        >>> dt.tzinfo == UTC
        True
    """
    if iso_string.endswith("Z"):
        iso_string = iso_string[:-1] + "+00:00"
    return datetime.fromisoformat(iso_string)


__all__ = [
    "UTC",
    "from_timestamp",
    "parse_iso_datetime",
    "utc_now",
]
