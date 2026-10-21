"""Environment configuration for operational service integration."""

from dataclasses import dataclass, field
from math import isfinite
from urllib.parse import urlsplit
import os
from typing import Self


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
            raise ValueError(
                "TRIP_CONTEXT_BASE_URL must be configured and not blank."
            )

        parsed_url = urlsplit(base_url)

        if (
            parsed_url.scheme not in ("http", "https")
            or not parsed_url.hostname
        ):
            raise ValueError(
                "TRIP_CONTEXT_BASE_URL must be an absolute HTTP or HTTPS URL."
            )

        timeout_seconds = float(
            os.environ.get("TRIP_CONTEXT_TIMEOUT_SECONDS", "3.0")
        )

        if not isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError(
                "TRIP_CONTEXT_TIMEOUT_SECONDS must be positive and finite."
            )

        token = os.environ.get("TRIP_CONTEXT_TOKEN")

        if token is not None and not token.strip():
            raise ValueError(
                "TRIP_CONTEXT_TOKEN must not be blank when configured."
            )

        return cls(
            base_url=base_url,
            token=token,
            timeout_seconds=timeout_seconds,
        )