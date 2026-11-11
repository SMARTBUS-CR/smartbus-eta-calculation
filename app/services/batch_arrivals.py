"""Calculate ordered ETA estimates from a resolved operational trip plan."""

from datetime import datetime, timedelta
from math import ceil

from app.schemas.batch_arrivals_schema import (
    ArrivalEstimate,
    ArrivalQualityReason,
    ArrivalTarget,
    BatchArrivalsAttributes,
    BatchArrivalsRequest,
)
from app.schemas.trip_context_schema import TripContext, TripStopOccurrence
from app.services.fallback import calculate_fallback_eta


MAX_FUTURE_SKEW = timedelta(seconds=5)
MAX_OBSERVATION_AGE_SECONDS = 30
MAX_ACCURACY_METERS = 100
DISTANCE_TOLERANCE_METERS = 1


class BatchInputError(ValueError):
    """The submitted progress or targets disagree with the trip plan."""

    def __init__(self, path: tuple[str | int, ...], detail: str) -> None:
        super().__init__(detail)
        self.path = path
        self.detail = detail


class TripNotEstimable(ValueError):
    """The trip has ended and can no longer be estimated."""


def calculate_batch_arrivals(
    payload: BatchArrivalsRequest, context: TripContext, *, calculated_at: datetime
) -> BatchArrivalsAttributes:
    """Calculate all estimates with one server clock reading."""
    for instant, path in (
        (payload.observed_at, ("observed_at",)),
        (payload.tracking.effective_speed_observed_at, ("tracking", "effective_speed_observed_at")),
    ):
        if instant is not None and instant - calculated_at > MAX_FUTURE_SKEW:
            raise BatchInputError(path, "errors.arrivals.future_observation")

    targets = _validate_targets(payload, context)
    if context.status in ("completed", "cancelled"):
        raise TripNotEstimable("The trip has ended.")

    source_age = max(0.0, (calculated_at - payload.observed_at).total_seconds())
    problem = _observation_problem(payload, context, source_age)
    speed = payload.tracking.current_speed_kmh
    confirmed = payload.tracking.confirmed_stop_occurrence_id
    confirmed_at = min(payload.observed_at, calculated_at)
    arrivals = [
        _estimate_arrival(
            target,
            stop,
            calculated_at,
            speed,
            problem,
            confirmed_at if confirmed == stop.occurrence_id else None,
        )
        for target, stop in targets
    ]
    return BatchArrivalsAttributes(
        contract_version=1,
        trip_id=context.trip_id,
        route_revision=context.route_revision,
        position_version=payload.position_version,
        observed_at=payload.observed_at,
        calculated_at=calculated_at,
        source_age_seconds=source_age,
        arrivals=arrivals,
    )


def _validate_targets(
    payload: BatchArrivalsRequest, context: TripContext
) -> list[tuple[ArrivalTarget, TripStopOccurrence]]:
    progress = payload.tracking.distance_along_route_m
    if progress > context.route_distance_m:
        raise BatchInputError(
            ("tracking", "distance_along_route_m"), "errors.arrivals.progress_outside_route"
        )

    confirmed = payload.tracking.confirmed_stop_occurrence_id
    if confirmed is not None and all(target.stop_occurrence_id != confirmed for target in payload.targets):
        raise BatchInputError(
            ("tracking", "confirmed_stop_occurrence_id"), "errors.arrivals.confirmed_target_missing"
        )

    occurrences = {stop.occurrence_id: stop for stop in context.stop_occurrences}
    matched = []
    previous_sequence = 0
    for index, target in enumerate(payload.targets):
        occurrence_path = ("targets", index, "stop_occurrence_id")
        distance_path = ("targets", index, "remaining_distance_m")
        stop = occurrences.get(target.stop_occurrence_id)
        if stop is None:
            raise BatchInputError(occurrence_path, "errors.arrivals.unknown_occurrence")
        if stop.stop_sequence <= previous_sequence:
            raise BatchInputError(occurrence_path, "errors.arrivals.occurrence_order")

        remaining = stop.distance_along_route_m - progress
        if target.stop_occurrence_id == confirmed:
            if target.remaining_distance_m != 0 or abs(remaining) > DISTANCE_TOLERANCE_METERS:
                raise BatchInputError(distance_path, "errors.arrivals.confirmed_distance")
        elif remaining < 0:
            raise BatchInputError(occurrence_path, "errors.arrivals.occurrence_passed")
        elif abs(remaining - target.remaining_distance_m) > DISTANCE_TOLERANCE_METERS:
            raise BatchInputError(distance_path, "errors.arrivals.distance_mismatch")

        matched.append((target, stop))
        previous_sequence = stop.stop_sequence
    return matched


def _observation_problem(
    payload: BatchArrivalsRequest, context: TripContext, source_age: float
) -> ArrivalQualityReason | None:
    tracking = payload.tracking
    if context.status == "scheduled":
        return "trip_not_started"
    if source_age > MAX_OBSERVATION_AGE_SECONDS:
        return "stale_observation"
    if not tracking.on_route:
        return "off_route"
    if tracking.accuracy_meters is None or tracking.accuracy_meters > MAX_ACCURACY_METERS:
        return "poor_accuracy"
    return None


def _estimate_arrival(
    target: ArrivalTarget,
    stop: TripStopOccurrence,
    calculated_at: datetime,
    speed: float | None,
    problem: ArrivalQualityReason | None,
    confirmed_at: datetime | None,
) -> ArrivalEstimate:
    seconds = None
    arrival_at = None
    reason = problem
    if reason is None:
        if confirmed_at is not None:
            seconds = 0
            arrival_at = confirmed_at
            reason = "confirmed_arrival"
        elif target.remaining_distance_m == 0:
            reason = "arrival_unconfirmed"
        elif speed is None or speed == 0:
            reason = "no_usable_speed"
        else:
            try:
                estimate = ceil(calculate_fallback_eta(target.remaining_distance_m, speed))
                arrival_at = calculated_at + timedelta(seconds=estimate)
                seconds = estimate
            except (ValueError, OverflowError):
                reason = "calculation_unavailable"

    if reason == "confirmed_arrival":
        method = "arrived"
    elif seconds is not None:
        method = "distance_speed"
    elif stop.planned_arrival_at is not None and reason != "calculation_unavailable":
        method = "scheduled_reference"
    else:
        method = "unavailable"
    return ArrivalEstimate(
        stop_occurrence_id=stop.occurrence_id,
        stop_id=stop.stop_id,
        stop_sequence=stop.stop_sequence,
        remaining_distance_m=target.remaining_distance_m,
        eta_seconds=seconds,
        arrival_at=arrival_at,
        planned_arrival_at=stop.planned_arrival_at,
        method=method,
        quality_reason=reason or "current_speed",
        model_version=None,
    )
