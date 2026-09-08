"""Deterministic ETA calculation using distance and constant speed."""

from math import isfinite


def calculate_fallback_eta(
    distancia_restante_m: float,
    velocidad_actual_kmh: float,
) -> float:
    """Return ETA in seconds for a finite distance and positive finite speed.

    Raise ValueError for invalid mathematical inputs or an unrepresentable ETA.
    A stopped bus has no finite ETA under this constant-speed calculation.
    """
    if not isfinite(distancia_restante_m) or distancia_restante_m < 0:
        raise ValueError("distancia_restante_m must be finite and non-negative")
    if not isfinite(velocidad_actual_kmh) or velocidad_actual_kmh <= 0:
        raise ValueError("velocidad_actual_kmh must be finite and positive")

    velocidad_m_s = velocidad_actual_kmh / 3.6
    if velocidad_m_s == 0:
        raise ValueError("velocidad_actual_kmh is too small to calculate ETA")

    eta_segundos = distancia_restante_m / velocidad_m_s
    if not isfinite(eta_segundos):
        raise ValueError("ETA exceeds the finite numeric range")

    return eta_segundos
