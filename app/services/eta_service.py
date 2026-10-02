"""ETA orchestration that prefers ML predictions and falls back safely."""

from datetime import datetime, timezone
from math import isfinite

from app.services.fallback import calculate_fallback_eta
from app.services.ml_model import predict_eta


ML_CONFIDENCE = 0.82
FALLBACK_CONFIDENCE = 0.50


class EtaCalculationError(RuntimeError):
    """Neither ETA calculation strategy could return a valid result."""


def format_eta(eta_seconds: int) -> str:
    """Format a non-negative ETA as minutes and seconds."""
    minutes, seconds = divmod(eta_seconds, 60)
    return f"{minutes} min {seconds} s"


def _normalize_eta_seconds(value: float) -> int:
    """Return a finite, non-negative ETA rounded to whole seconds."""
    eta_seconds = float(value)
    if not isfinite(eta_seconds) or eta_seconds < 0:
        raise ValueError("ETA must be finite and non-negative")
    return round(eta_seconds)


def _utc_timestamp() -> str:
    """Return the current UTC time in ISO 8601 format with a Z suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def calculate_eta(
    remaining_distance_m: float,
    current_speed_kmh: float,
    route_id: str,
    stop_id: str,
) -> dict[str, float | int | str]:
    """Calculate ETA using ML first, then the deterministic fallback.

    Confidence is an application-level indicator for this MVP. It is not a
    statistically calibrated probability.
    """
    try:
        speed_m_s = current_speed_kmh / 3.6
    except (TypeError, ValueError) as exc:
        raise EtaCalculationError("Current speed cannot be converted to m/s") from exc

    try:
        eta_seconds = _normalize_eta_seconds(
            predict_eta(remaining_distance_m, current_speed_kmh)
        )
        confidence = ML_CONFIDENCE
    except Exception:
        try:
            eta_seconds = _normalize_eta_seconds(
                calculate_fallback_eta(remaining_distance_m, current_speed_kmh)
            )
            confidence = FALLBACK_CONFIDENCE
        except Exception as exc:
            raise EtaCalculationError("ETA calculation failed") from exc

    return {
        "remaining_distance_m": remaining_distance_m,
        "current_speed_kmh": current_speed_kmh,
        "speed_m_s": speed_m_s,
        "eta_seconds": eta_seconds,
        "eta_format": format_eta(eta_seconds),
        "confidence": confidence,
        "calculated_at": _utc_timestamp(),
        "route_id": route_id,
        "stop_id": stop_id,
    }
