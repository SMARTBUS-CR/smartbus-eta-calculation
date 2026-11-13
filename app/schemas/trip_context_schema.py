"""Typed contracts for operational Trip plans."""

from datetime import date, datetime, timezone
from typing import Annotated, Any, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

Longitude = Annotated[
    float,
    Field(
        ge=-180,
        le=180,
        allow_inf_nan=False,
        strict=True,
    ),
]

Latitude = Annotated[
    float,
    Field(
        ge=-90,
        le=90,
        allow_inf_nan=False,
        strict=True,
    ),
]


def parse_planned_timestamp(value: Any) -> datetime:
    """Parse ISO 8601 text without accepting Unix timestamps."""

    if isinstance(value, datetime):
        return value

    if not isinstance(value, str):
        raise ValueError("Planned timestamps must use ISO 8601 format.")

    try:
        return datetime.fromisoformat(value)
    except ValueError as exception:
        raise ValueError("Planned timestamps must use ISO 8601 format.") from exception


class RouteGeometry(BaseModel):
    """Road geometry preserved in the Trip plan."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["LineString"]
    coordinates: list[tuple[Longitude, Latitude]] = Field(min_length=2)


class TripStopOccurrence(BaseModel):
    """One visit to a physical stop within a Trip."""

    model_config = ConfigDict(extra="forbid")

    occurrence_id: UUID
    stop_id: UUID
    stop_sequence: int = Field(gt=0, strict=True)
    name: str
    latitude: Latitude
    longitude: Longitude
    distance_along_route_m: float = Field(
        ge=0,
        allow_inf_nan=False,
        strict=True,
    )
    planned_arrival_at: AwareDatetime | None

    @field_validator("planned_arrival_at", mode="after")
    @classmethod
    def normalize_planned_arrival_to_utc(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """Normalize known stop arrival instants to UTC."""

        if value is None:
            return None

        return value.astimezone(timezone.utc)

    @field_validator("planned_arrival_at", mode="before")
    @classmethod
    def parse_planned_arrival(cls, value: Any) -> datetime | None:
        """Parse a known arrival while preserving unknown times."""

        if value is None:
            return None

        return parse_planned_timestamp(value)


class TripContext(BaseModel):
    """Versioned operational context consumed by ETA."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[1]
    trip_id: UUID
    company_id: UUID
    route_pattern_id: UUID
    route_revision: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    status: Literal[
        "scheduled",
        "in_progress",
        "completed",
        "cancelled",
    ]
    service_date: date
    timezone: str
    planned_departure_at: AwareDatetime
    planned_arrival_at: AwareDatetime
    route_geometry: RouteGeometry
    route_distance_m: float = Field(
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    stop_occurrences: list[TripStopOccurrence] = Field(min_length=2)

    @field_validator("stop_occurrences")
    @classmethod
    def validate_unique_occurrence_ids(
        cls,
        occurrences: list[TripStopOccurrence],
    ) -> list[TripStopOccurrence]:
        """Reject repeated occurrence identities within a Trip."""

        occurrence_ids = [occurrence.occurrence_id for occurrence in occurrences]

        if len(occurrence_ids) != len(set(occurrence_ids)):
            raise ValueError("Stop occurrence IDs must be unique.")

        return occurrences

    @field_validator("stop_occurrences")
    @classmethod
    def validate_increasing_stop_sequences(
        cls,
        occurrences: list[TripStopOccurrence],
    ) -> list[TripStopOccurrence]:
        """Require stop sequences to increase in travel order."""

        for previous, current in zip(occurrences, occurrences[1:]):
            if current.stop_sequence <= previous.stop_sequence:
                raise ValueError("Stop sequences must be strictly increasing.")

        return occurrences

    @field_validator("stop_occurrences")
    @classmethod
    def validate_non_decreasing_occurrence_distances(
        cls,
        occurrences: list[TripStopOccurrence],
    ) -> list[TripStopOccurrence]:
        """Require cumulative distances to follow travel order."""

        for previous, current in zip(occurrences, occurrences[1:]):
            if current.distance_along_route_m < previous.distance_along_route_m:
                raise ValueError("Stop occurrence distances must be non-decreasing.")

        return occurrences

    @field_validator(
        "planned_departure_at",
        "planned_arrival_at",
        mode="after",
    )
    @classmethod
    def normalize_planned_timestamps_to_utc(
        cls,
        value: datetime,
    ) -> datetime:
        """Normalize planned Trip instants to UTC."""

        return value.astimezone(timezone.utc)

    @field_validator(
        "planned_departure_at",
        "planned_arrival_at",
        mode="before",
    )
    @classmethod
    def parse_planned_timestamps(cls, value: Any) -> datetime:
        """Parse planned Trip instants before timezone validation."""

        return parse_planned_timestamp(value)

    @field_validator("contract_version", mode="before")
    @classmethod
    def validate_contract_version_type(cls, value: Any) -> int:
        """Require an integer before checking the supported version."""

        if type(value) is not int:
            raise ValueError("Contract version must be an integer.")

        return value

    @field_validator("timezone")
    @classmethod
    def validate_company_timezone(cls, value: str) -> str:
        """Require a recognized IANA timezone identifier."""

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exception:
            raise ValueError("Company timezone must be a valid IANA identifier.") from exception

        return value

    @model_validator(mode="after")
    def validate_occurrence_distance_bounds(self) -> Self:
        """Keep stop occurrence distances within the route length."""

        for occurrence in self.stop_occurrences:
            if occurrence.distance_along_route_m > self.route_distance_m:
                raise ValueError("Stop occurrence distances must not exceed the route length.")

        return self

    @model_validator(mode="after")
    def validate_planned_trip_interval(self) -> Self:
        """Require planned arrival to follow planned departure."""

        if self.planned_arrival_at <= self.planned_departure_at:
            raise ValueError("Planned arrival must be after planned departure.")

        return self

    @model_validator(mode="after")
    def validate_occurrence_time_bounds(self) -> Self:
        """Keep known stop times within the planned Trip interval."""

        for occurrence in self.stop_occurrences:
            arrival = occurrence.planned_arrival_at

            if arrival is None:
                continue

            if not (self.planned_departure_at <= arrival <= self.planned_arrival_at):
                raise ValueError("Stop occurrence times must be within the planned Trip interval.")

        return self

    @model_validator(mode="after")
    def validate_non_decreasing_occurrence_times(self) -> Self:
        """Require known stop times to follow travel order."""

        previous_arrival = None

        for occurrence in self.stop_occurrences:
            arrival = occurrence.planned_arrival_at

            if arrival is None:
                continue

            if previous_arrival is not None and arrival < previous_arrival:
                raise ValueError("Stop occurrence times must be non-decreasing.")

            previous_arrival = arrival

        return self
