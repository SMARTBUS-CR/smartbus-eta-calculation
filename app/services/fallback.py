"""Deterministic ETA calculation using distance and constant speed."""

from math import isfinite


def calculate_fallback_eta(
    remaining_distance_m: float,
    current_speed_kmh: float,
) -> float:
    """Return ETA in seconds for a finite distance and positive finite speed.

    Raise ValueError for invalid mathematical inputs or an unrepresentable ETA.
    A stopped bus has no finite ETA under this constant-speed calculation.
    """
    if not isfinite(remaining_distance_m) or remaining_distance_m < 0:
        raise ValueError("remaining_distance_m must be finite and non-negative")
    if not isfinite(current_speed_kmh) or current_speed_kmh <= 0:
        raise ValueError("current_speed_kmh must be finite and positive")

    speed_m_s = current_speed_kmh / 3.6
    if speed_m_s == 0:
        raise ValueError("current_speed_kmh is too small to calculate ETA")

    eta_seconds = remaining_distance_m / speed_m_s
    if not isfinite(eta_seconds):
        raise ValueError("ETA exceeds the finite numeric range")

    return eta_seconds
