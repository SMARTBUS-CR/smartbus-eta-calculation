from datetime import datetime, timezone

def calculate_eta(remaining_distance_m: float, current_speed_kmh: float, route_id: str, stop_id: str, lang: str = "en") -> dict:
    """
    Mock integration for ETA calculation service.
    This will be replaced by the actual ML/Fallback logic.
    """
    # Simulate a basic calculation or fallback
    eta_seconds = 600 if remaining_distance_m > 0 else 0
    confidence = 0.82
    
    minutes = eta_seconds // 60
    unit_label = "min" if "es" in lang.lower() else "min"
    
    return {
        "eta_seconds": eta_seconds,
        "eta_format": f"{minutes} {unit_label} 0 s",
        "confidence": confidence,
        "calculated_at": datetime.now(timezone.utc).isoformat()
    }