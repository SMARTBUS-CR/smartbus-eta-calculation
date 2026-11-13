"""Environment configuration for ETA and its operational dependencies."""

import os
from dataclasses import dataclass, field
from math import isfinite
from typing import Self
from urllib.parse import urlsplit


@dataclass(frozen=True)
class TripContextSettings:
    """Connection settings for the operational Trip context provider."""

    base_url: str
    token: str | None = field(default=None, repr=False)
    timeout_seconds: float = 3.0

    @classmethod
    def from_environment(cls) -> Self:
        """Read provider settings when explicitly requested."""

        base_url = os.environ.get("TRIP_CONTEXT_BASE_URL", "")

        if not base_url.strip():
            raise ValueError("TRIP_CONTEXT_BASE_URL must be configured and not blank.")

        parsed_url = urlsplit(base_url)

        if parsed_url.scheme not in ("http", "https") or not parsed_url.hostname:
            raise ValueError("TRIP_CONTEXT_BASE_URL must be an absolute HTTP or HTTPS URL.")

        timeout_seconds = float(os.environ.get("TRIP_CONTEXT_TIMEOUT_SECONDS", "3.0"))

        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("TRIP_CONTEXT_TIMEOUT_SECONDS must be positive and finite.")

        token = os.environ.get("TRIP_CONTEXT_TOKEN")
        token = token.strip() if token is not None and token.strip() else None

        return cls(
            base_url=base_url,
            token=token,
            timeout_seconds=timeout_seconds,
        )


@dataclass(frozen=True)
class ArrivalQualityPolicy:
    """Maximum source age, skew and inaccuracy accepted for live arrivals."""

    max_observation_age_seconds: float = 30
    max_future_skew_seconds: float = 5
    max_accuracy_meters: float = 100
    max_effective_speed_age_seconds: float = 30

    @classmethod
    def from_environment(cls) -> Self:
        defaults = cls()
        return cls(
            max_observation_age_seconds=_quality_limit(
                "ETA_MAX_OBSERVATION_AGE_SECONDS", defaults.max_observation_age_seconds
            ),
            max_future_skew_seconds=_quality_limit(
                "ETA_MAX_FUTURE_SKEW_SECONDS", defaults.max_future_skew_seconds
            ),
            max_accuracy_meters=_quality_limit(
                "ETA_MAX_ACCURACY_METERS", defaults.max_accuracy_meters
            ),
            max_effective_speed_age_seconds=_quality_limit(
                "ETA_MAX_EFFECTIVE_SPEED_AGE_SECONDS", defaults.max_effective_speed_age_seconds
            ),
        )


def _quality_limit(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default

    message = f"{name} must be a finite, nonnegative number."
    try:
        limit = float(raw)
    except ValueError as error:
        raise ValueError(message) from error
    if not isfinite(limit) or limit < 0:
        raise ValueError(message)
    return limit
