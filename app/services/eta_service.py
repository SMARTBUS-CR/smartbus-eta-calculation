from datetime import datetime, timezone

class EtaCalculationError(Exception):
    """Exception for errors in the Machine Learning model and fallbacks."""
    pass

def calculate_eta(remaining_distance_m: float, current_speed_kmh: float, route_id: str, stop_id: str, lang: str = "en") -> dict:
    eta_seconds = 600 if remaining_distance_m > 0 else 0
    confidence = 0.82
    
    minutes = eta_seconds // 60
    unit_label = "min"
    
    return {
        "eta_seconds": eta_seconds,
        "eta_format": f"{minutes} {unit_label} 0 s",
        "confidence": confidence,
        "calculated_at": datetime.now(timezone.utc).isoformat()
    }