"""Tests for src/rag_processor/utils/time_utils.py."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from rag_processor.utils.time_utils import UTC, from_timestamp, parse_iso_datetime, utc_now


class TestUTCConstant:
    def test_utc_is_timezone_utc(self) -> None:
        assert UTC is timezone.utc


class TestUtcNow:
    def test_returns_datetime(self) -> None:
        result = utc_now()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self) -> None:
        result = utc_now()
        assert result.tzinfo is not None

    def test_timezone_is_utc(self) -> None:
        result = utc_now()
        assert result.tzinfo == UTC


class TestFromTimestamp:
    def test_known_epoch_zero(self) -> None:
        result = from_timestamp(0)
        assert result.year == 1970
        assert result.month == 1
        assert result.day == 1
        assert result.tzinfo == UTC

    def test_known_timestamp(self) -> None:
        # 2022-01-01 00:00:00 UTC
        result = from_timestamp(1640995200)
        assert result.year == 2022
        assert result.month == 1
        assert result.day == 1

    def test_round_trip_with_utc_now(self) -> None:
        now = utc_now()
        ts = now.timestamp()
        recovered = from_timestamp(ts)
        assert abs((recovered - now).total_seconds()) < 0.001

    def test_accepts_float(self) -> None:
        result = from_timestamp(1640995200.5)
        assert result.microsecond > 0

    def test_accepts_int(self) -> None:
        result = from_timestamp(1640995200)
        assert isinstance(result, datetime)


class TestParseIsoDatetime:
    def test_z_suffix(self) -> None:
        result = parse_iso_datetime("2024-01-01T12:00:00Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.tzinfo == UTC

    def test_plus_offset(self) -> None:
        result = parse_iso_datetime("2024-06-15T08:30:00+00:00")
        assert result.year == 2024
        assert result.month == 6
        assert result.hour == 8
        assert result.minute == 30

    def test_z_and_offset_produce_same_result(self) -> None:
        with_z = parse_iso_datetime("2024-03-01T00:00:00Z")
        with_offset = parse_iso_datetime("2024-03-01T00:00:00+00:00")
        assert with_z == with_offset

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_iso_datetime("not-a-datetime")

    def test_timezone_aware(self) -> None:
        result = parse_iso_datetime("2024-01-01T00:00:00Z")
        assert result.tzinfo is not None
