def make_trip_context_payload():
    """Return a valid Trip plan with two visits to the same stop."""

    stop_id = "55555555-5555-4555-8555-555555555555"
    first_occurrence_id = "44444444-4444-4444-8444-444444444441"
    last_occurrence_id = "44444444-4444-4444-8444-444444444442"

    return {
        "contract_version": 1,
        "trip_id": "11111111-1111-4111-8111-111111111111",
        "company_id": "22222222-2222-4222-8222-222222222222",
        "route_pattern_id": "33333333-3333-4333-8333-333333333333",
        "route_revision": "a" * 64,
        "status": "in_progress",
        "service_date": "2026-10-21",
        "timezone": "America/Costa_Rica",
        "planned_departure_at": "2026-10-21T15:00:00Z",
        "planned_arrival_at": "2026-10-21T15:30:00Z",
        "route_geometry": {
            "type": "LineString",
            "coordinates": [
                [-84.0, 10.0],
                [-84.0, 10.01],
                [-84.0, 10.0],
            ],
        },
        "route_distance_m": 2223.9,
        "stop_occurrences": [
            {
                "occurrence_id": first_occurrence_id,
                "stop_id": stop_id,
                "stop_sequence": 1,
                "name": "Central Terminal",
                "latitude": 10.0,
                "longitude": -84.0,
                "distance_along_route_m": 0.0,
                "planned_arrival_at": "2026-10-21T15:00:00Z",
            },
            {
                "occurrence_id": last_occurrence_id,
                "stop_id": stop_id,
                "stop_sequence": 2,
                "name": "Central Terminal",
                "latitude": 10.0,
                "longitude": -84.0,
                "distance_along_route_m": 2223.9,
                "planned_arrival_at": "2026-10-21T15:30:00Z",
            },
        ],
    }
