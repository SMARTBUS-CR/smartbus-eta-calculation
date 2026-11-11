"""Request and response contracts for the versioned arrival estimates API."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    ValidationInfo,
    field_validator,
)


def parse_instant(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError("An ISO 8601 timestamp with a timezone is required.")
    return datetime.fromisoformat(value)


def to_utc(value: datetime) -> datetime:
    try:
        return value.astimezone(timezone.utc)
    except OverflowError as error:
        raise ValueError("The timestamp is outside the supported UTC range.") from error


UtcInstant = Annotated[AwareDatetime, BeforeValidator(parse_instant), AfterValidator(to_utc)]
Meters = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
SpeedKmh = Annotated[float, Field(strict=True, ge=0, le=400, allow_inf_nan=False)]
RouteRevision = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")]


class TrackingProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    on_route: StrictBool
    accuracy_meters: Meters | None
    current_speed_kmh: SpeedKmh | None
    effective_speed_kmh: SpeedKmh | None
    effective_speed_observed_at: UtcInstant | None
    distance_along_route_m: Meters
    confirmed_stop_occurrence_id: UUID | None

    @field_validator("effective_speed_observed_at")
    @classmethod
    def require_speed_and_timestamp_together(
        cls, observed_at: datetime | None, info: ValidationInfo
    ) -> datetime | None:
        if "effective_speed_kmh" in info.data:
            speed = info.data["effective_speed_kmh"]
            if (speed is None) != (observed_at is None):
                raise ValueError("Effective speed and its timestamp must be provided together.")
        return observed_at


class ArrivalTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_occurrence_id: UUID
    remaining_distance_m: Meters


class BatchArrivalsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[1]
    route_revision: RouteRevision
    position_version: int = Field(strict=True, gt=0)
    observed_at: UtcInstant
    tracking: TrackingProgress
    targets: list[ArrivalTarget] = Field(min_length=1, max_length=100)

    @field_validator("contract_version", mode="before")
    @classmethod
    def require_integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Contract version must be an integer.")
        return value


ArrivalQualityReason = Literal[
    "current_speed",
    "recent_effective_speed",
    "confirmed_arrival",
    "trip_not_started",
    "stale_observation",
    "off_route",
    "poor_accuracy",
    "no_usable_speed",
    "arrival_unconfirmed",
    "calculation_unavailable",
]


class ArrivalEstimate(BaseModel):
    stop_occurrence_id: UUID
    stop_id: UUID
    stop_sequence: int = Field(gt=0)
    remaining_distance_m: Meters
    eta_seconds: Annotated[int, Field(ge=0)] | None
    arrival_at: UtcInstant | None
    planned_arrival_at: UtcInstant | None
    method: Literal["distance_speed", "arrived", "scheduled_reference", "unavailable"]
    quality_reason: ArrivalQualityReason
    model_version: str | None


class BatchArrivalsAttributes(BaseModel):
    contract_version: Literal[1]
    trip_id: UUID
    route_revision: RouteRevision
    position_version: int = Field(gt=0)
    observed_at: UtcInstant
    calculated_at: UtcInstant
    source_age_seconds: float = Field(ge=0, allow_inf_nan=False)
    arrivals: list[ArrivalEstimate]


class BatchArrivalsData(BaseModel):
    type: Literal["trip-arrival-estimates"]
    id: UUID
    attributes: BatchArrivalsAttributes


class BatchArrivalsResponse(BaseModel):
    data: BatchArrivalsData


_EXAMPLE_TRIP = "11111111-1111-4111-8111-111111111111"
_EXAMPLE_OCCURRENCE = "44444444-4444-4444-8444-444444444442"
_EXAMPLE_REVISION = "a" * 64

ARRIVALS_REQUEST_EXAMPLE = {
    "contract_version": 1,
    "route_revision": _EXAMPLE_REVISION,
    "position_version": 12,
    "observed_at": "2026-10-21T15:05:00Z",
    "tracking": {
        "on_route": True,
        "accuracy_meters": 12.0,
        "current_speed_kmh": 36.0,
        "effective_speed_kmh": None,
        "effective_speed_observed_at": None,
        "distance_along_route_m": 1212.16,
        "confirmed_stop_occurrence_id": None,
    },
    "targets": [
        {"stop_occurrence_id": _EXAMPLE_OCCURRENCE, "remaining_distance_m": 1000.0}
    ],
}

ARRIVALS_RESPONSE_EXAMPLE = {
    "data": {
        "type": "trip-arrival-estimates",
        "id": _EXAMPLE_TRIP,
        "attributes": {
            "contract_version": 1,
            "trip_id": _EXAMPLE_TRIP,
            "route_revision": _EXAMPLE_REVISION,
            "position_version": 12,
            "observed_at": "2026-10-21T15:05:00Z",
            "calculated_at": "2026-10-21T15:05:00Z",
            "source_age_seconds": 0.0,
            "arrivals": [
                {
                    "stop_occurrence_id": _EXAMPLE_OCCURRENCE,
                    "stop_id": "55555555-5555-4555-8555-555555555552",
                    "stop_sequence": 2,
                    "remaining_distance_m": 1000.0,
                    "eta_seconds": 100,
                    "arrival_at": "2026-10-21T15:06:40Z",
                    "planned_arrival_at": "2026-10-21T15:30:00Z",
                    "method": "distance_speed",
                    "quality_reason": "current_speed",
                    "model_version": None,
                }
            ],
        },
    },
}
