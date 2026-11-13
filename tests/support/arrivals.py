"""Fixtures shared by the batch ETA contract and calculation tests."""

from tests.support.trip_context import make_trip_context_payload


def make_arrivals_plan():
    plan = make_trip_context_payload()
    plan["route_distance_m"] = 3000.0
    for stop, distance in zip(plan["stop_occurrences"], (1000.0, 2500.0)):
        stop["distance_along_route_m"] = distance
    return plan


def make_arrivals_payload():
    plan = make_arrivals_plan()
    return {
        "contract_version": 1,
        "route_revision": plan["route_revision"],
        "position_version": 12,
        "observed_at": "2026-10-21T15:05:00Z",
        "tracking": {
            "on_route": True,
            "accuracy_meters": 12.0,
            "current_speed_kmh": 36.0,
            "effective_speed_kmh": None,
            "effective_speed_observed_at": None,
            "distance_along_route_m": 0.0,
            "confirmed_stop_occurrence_id": None,
        },
        "targets": [
            {
                "stop_occurrence_id": stop["occurrence_id"],
                "remaining_distance_m": stop["distance_along_route_m"],
            }
            for stop in plan["stop_occurrences"]
        ],
    }


def make_confirmed_arrival_payload():
    payload = make_arrivals_payload()
    confirmed, upcoming = payload["targets"]
    progress = confirmed["remaining_distance_m"]
    payload["tracking"].update(
        current_speed_kmh=0.0,
        distance_along_route_m=progress,
        confirmed_stop_occurrence_id=confirmed["stop_occurrence_id"],
    )
    confirmed["remaining_distance_m"] = 0.0
    upcoming["remaining_distance_m"] -= progress
    return payload
