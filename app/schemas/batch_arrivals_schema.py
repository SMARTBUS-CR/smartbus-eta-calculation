"""Request contract for the versioned arrival estimates API."""

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
    return value.astimezone(timezone.utc)


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
