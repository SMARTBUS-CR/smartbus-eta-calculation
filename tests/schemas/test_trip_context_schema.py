"""Tests for the operational Trip context contract."""

import unittest
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError

from app.schemas.trip_context_schema import TripContext
from tests.support.trip_context import make_trip_context_payload


class TripContextSchemaTests(unittest.TestCase):
    """Verify typed Trip plans and independent stop occurrences."""

    def test_preserves_ordered_occurrences_of_the_same_physical_stop(self):
        payload = make_trip_context_payload()
        first_occurrence_id = payload["stop_occurrences"][0]["occurrence_id"]
        last_occurrence_id = payload["stop_occurrences"][1]["occurrence_id"]
        stop_id = payload["stop_occurrences"][0]["stop_id"]

        context = TripContext.model_validate(payload)

        self.assertEqual(context.trip_id, UUID(payload["trip_id"]))
        self.assertEqual(context.route_revision, payload["route_revision"])
        self.assertEqual(
            context.planned_departure_at,
            datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            [item.occurrence_id for item in context.stop_occurrences],
            [UUID(first_occurrence_id), UUID(last_occurrence_id)],
        )
        self.assertEqual(
            [item.stop_id for item in context.stop_occurrences],
            [UUID(stop_id), UUID(stop_id)],
        )
        self.assertEqual(
            [item.stop_sequence for item in context.stop_occurrences],
            [1, 2],
        )
        self.assertEqual(
            [item.distance_along_route_m for item in context.stop_occurrences],
            [0.0, 2223.9],
        )

    def test_rejects_duplicate_occurrence_ids(self):
        payload = make_trip_context_payload()
        payload["stop_occurrences"][1]["occurrence_id"] = payload["stop_occurrences"][0][
            "occurrence_id"
        ]

        with self.assertRaises(ValidationError) as raised:
            TripContext.model_validate(payload)

        self.assertTrue(
            any("stop_occurrences" in error["loc"] for error in raised.exception.errors())
        )

    def test_rejects_non_increasing_stop_sequences(self):
        for sequences in ([1, 1], [2, 1]):
            with self.subTest(sequences=sequences):
                payload = make_trip_context_payload()

                for occurrence, sequence in zip(
                    payload["stop_occurrences"],
                    sequences,
                ):
                    occurrence["stop_sequence"] = sequence

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any("stop_occurrences" in error["loc"] for error in raised.exception.errors())
                )

    def test_rejects_plans_with_fewer_than_two_stop_occurrences(self):
        for count in (0, 1):
            with self.subTest(count=count):
                payload = make_trip_context_payload()
                payload["stop_occurrences"] = payload["stop_occurrences"][:count]

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any("stop_occurrences" in error["loc"] for error in raised.exception.errors())
                )

    def test_rejects_non_positive_stop_sequences(self):
        for sequence in (0, -1):
            with self.subTest(sequence=sequence):
                payload = make_trip_context_payload()
                payload["stop_occurrences"][0]["stop_sequence"] = sequence

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(
                        error["loc"] == ("stop_occurrences", 0, "stop_sequence")
                        for error in raised.exception.errors()
                    )
                )

    def test_rejects_invalid_occurrence_distances(self):
        for distance in (
            -1.0,
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(distance=distance):
                payload = make_trip_context_payload()
                payload["stop_occurrences"][0]["distance_along_route_m"] = distance

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(
                        error["loc"]
                        == (
                            "stop_occurrences",
                            0,
                            "distance_along_route_m",
                        )
                        for error in raised.exception.errors()
                    )
                )

    def test_rejects_decreasing_occurrence_distances(self):
        payload = make_trip_context_payload()
        payload["stop_occurrences"][0]["distance_along_route_m"] = 100.0
        payload["stop_occurrences"][1]["distance_along_route_m"] = 50.0

        with self.assertRaises(ValidationError) as raised:
            TripContext.model_validate(payload)

        self.assertTrue(
            any("stop_occurrences" in error["loc"] for error in raised.exception.errors())
        )

    def test_rejects_invalid_route_distances(self):
        for distance in (
            0.0,
            -1.0,
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with self.subTest(distance=distance):
                payload = make_trip_context_payload()
                payload["route_distance_m"] = distance

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(
                        error["loc"] == ("route_distance_m",) for error in raised.exception.errors()
                    )
                )

    def test_rejects_occurrence_distance_beyond_route_length(self):
        payload = make_trip_context_payload()
        payload["stop_occurrences"][-1]["distance_along_route_m"] = (
            payload["route_distance_m"] + 1.0
        )

        with self.assertRaises(ValidationError):
            TripContext.model_validate(payload)

    def test_rejects_geometry_with_fewer_than_two_positions(self):
        for count in (0, 1):
            with self.subTest(count=count):
                payload = make_trip_context_payload()
                payload["route_geometry"]["coordinates"] = payload["route_geometry"]["coordinates"][
                    :count
                ]

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(
                        error["loc"] == ("route_geometry", "coordinates")
                        for error in raised.exception.errors()
                    )
                )

    def test_rejects_invalid_geometry_coordinates(self):
        invalid_coordinates = (
            (0, -180.1),
            (0, 180.1),
            (1, -90.1),
            (1, 90.1),
            (0, float("nan")),
            (0, float("inf")),
            (1, float("-inf")),
        )

        for axis, value in invalid_coordinates:
            with self.subTest(axis=axis, value=value):
                payload = make_trip_context_payload()
                payload["route_geometry"]["coordinates"][0][axis] = value

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(
                        error["loc"] == ("route_geometry", "coordinates", 0, axis)
                        for error in raised.exception.errors()
                    )
                )

    def test_rejects_invalid_stop_coordinates(self):
        invalid_coordinates = (
            ("longitude", -180.1),
            ("longitude", 180.1),
            ("latitude", -90.1),
            ("latitude", 90.1),
            ("longitude", float("nan")),
            ("longitude", float("inf")),
            ("latitude", float("-inf")),
        )

        for field, value in invalid_coordinates:
            with self.subTest(field=field, value=value):
                payload = make_trip_context_payload()
                payload["stop_occurrences"][0][field] = value

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(
                        error["loc"] == ("stop_occurrences", 0, field)
                        for error in raised.exception.errors()
                    )
                )

    def test_rejects_invalid_route_revisions(self):
        for revision in (
            "",
            "a" * 63,
            "a" * 65,
            "g" * 64,
            "A" * 64,
        ):
            with self.subTest(revision=revision):
                payload = make_trip_context_payload()
                payload["route_revision"] = revision

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(error["loc"] == ("route_revision",) for error in raised.exception.errors())
                )

    def test_rejects_planned_timestamps_without_timezone(self):
        for field in (
            "planned_departure_at",
            "planned_arrival_at",
        ):
            with self.subTest(field=field):
                payload = make_trip_context_payload()
                payload[field] = payload[field].removesuffix("Z")

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(error["loc"] == (field,) for error in raised.exception.errors())
                )

    def test_rejects_occurrence_timestamp_without_timezone(self):
        payload = make_trip_context_payload()
        occurrence = payload["stop_occurrences"][0]
        occurrence["planned_arrival_at"] = occurrence["planned_arrival_at"].removesuffix("Z")

        with self.assertRaises(ValidationError) as raised:
            TripContext.model_validate(payload)

        self.assertTrue(
            any(
                error["loc"] == ("stop_occurrences", 0, "planned_arrival_at")
                for error in raised.exception.errors()
            )
        )

    def test_rejects_planned_arrival_not_after_departure(self):
        for arrival in (
            "2026-10-21T15:00:00Z",
            "2026-10-21T14:59:00Z",
        ):
            with self.subTest(arrival=arrival):
                payload = make_trip_context_payload()
                payload["planned_arrival_at"] = arrival

                with self.assertRaises(ValidationError):
                    TripContext.model_validate(payload)

    def test_rejects_occurrence_times_outside_planned_interval(self):
        for index, arrival in (
            (0, "2026-10-21T14:59:00Z"),
            (1, "2026-10-21T15:31:00Z"),
        ):
            with self.subTest(index=index, arrival=arrival):
                payload = make_trip_context_payload()
                payload["stop_occurrences"][index]["planned_arrival_at"] = arrival

                with self.assertRaises(ValidationError):
                    TripContext.model_validate(payload)

    def test_rejects_decreasing_occurrence_times(self):
        payload = make_trip_context_payload()
        payload["stop_occurrences"][0]["planned_arrival_at"] = "2026-10-21T15:20:00Z"
        payload["stop_occurrences"][1]["planned_arrival_at"] = "2026-10-21T15:10:00Z"

        with self.assertRaises(ValidationError):
            TripContext.model_validate(payload)

    def test_normalizes_planned_trip_timestamps_to_utc(self):
        payload = make_trip_context_payload()
        payload["planned_departure_at"] = "2026-10-21T09:00:00-06:00"
        payload["planned_arrival_at"] = "2026-10-21T09:30:00-06:00"

        context = TripContext.model_validate(payload)
        serialized = context.model_dump(mode="json")

        self.assertEqual(
            serialized["planned_departure_at"],
            "2026-10-21T15:00:00Z",
        )
        self.assertEqual(
            serialized["planned_arrival_at"],
            "2026-10-21T15:30:00Z",
        )

    def test_normalizes_occurrence_timestamps_to_utc_and_preserves_null(self):
        payload = make_trip_context_payload()
        payload["stop_occurrences"][0]["planned_arrival_at"] = "2026-10-21T09:00:00-06:00"
        payload["stop_occurrences"][1]["planned_arrival_at"] = None

        context = TripContext.model_validate(payload)
        serialized = context.model_dump(mode="json")

        self.assertEqual(
            serialized["stop_occurrences"][0]["planned_arrival_at"],
            "2026-10-21T15:00:00Z",
        )
        self.assertIsNone(serialized["stop_occurrences"][1]["planned_arrival_at"])

    def test_rejects_non_integer_stop_sequences(self):
        for sequence in ("1", True, 1.0):
            with self.subTest(sequence=sequence):
                payload = make_trip_context_payload()
                payload["stop_occurrences"][0]["stop_sequence"] = sequence

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(
                        error["loc"] == ("stop_occurrences", 0, "stop_sequence")
                        for error in raised.exception.errors()
                    )
                )

    def test_rejects_non_numeric_distance_types(self):
        cases = (
            ("route", "2223.9"),
            ("route", True),
            ("occurrence", "0"),
            ("occurrence", False),
        )

        for target, value in cases:
            with self.subTest(target=target, value=value):
                payload = make_trip_context_payload()

                if target == "route":
                    payload["route_distance_m"] = value
                    expected_location = ("route_distance_m",)
                else:
                    payload["stop_occurrences"][0]["distance_along_route_m"] = value
                    expected_location = (
                        "stop_occurrences",
                        0,
                        "distance_along_route_m",
                    )

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(error["loc"] == expected_location for error in raised.exception.errors())
                )

    def test_rejects_non_numeric_coordinate_types(self):
        cases = (
            ("geometry", 0, "-84.0"),
            ("geometry", 1, True),
            ("stop", "longitude", "-84.0"),
            ("stop", "latitude", False),
        )

        for target, field, value in cases:
            with self.subTest(target=target, field=field, value=value):
                payload = make_trip_context_payload()

                if target == "geometry":
                    payload["route_geometry"]["coordinates"][0][field] = value
                    expected_location = (
                        "route_geometry",
                        "coordinates",
                        0,
                        field,
                    )
                else:
                    payload["stop_occurrences"][0][field] = value
                    expected_location = ("stop_occurrences", 0, field)

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(error["loc"] == expected_location for error in raised.exception.errors())
                )

    def test_rejects_invalid_contract_versions(self):
        for version in (0, 2, "1", True, 1.0):
            with self.subTest(version=version):
                payload = make_trip_context_payload()
                payload["contract_version"] = version

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(
                        error["loc"] == ("contract_version",) for error in raised.exception.errors()
                    )
                )

    def test_rejects_invalid_company_timezones(self):
        for timezone_name in ("", "Mars/Olympus_Mons", "-06:00"):
            with self.subTest(timezone=timezone_name):
                payload = make_trip_context_payload()
                payload["timezone"] = timezone_name

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(error["loc"] == ("timezone",) for error in raised.exception.errors())
                )

    def test_rejects_numeric_planned_timestamps(self):
        for target in ("departure", "arrival", "occurrence"):
            with self.subTest(target=target):
                payload = make_trip_context_payload()

                if target == "occurrence":
                    container = payload["stop_occurrences"][0]
                    field = "planned_arrival_at"
                    expected_location = ("stop_occurrences", 0, field)
                else:
                    container = payload
                    field = (
                        "planned_departure_at" if target == "departure" else "planned_arrival_at"
                    )
                    expected_location = (field,)

                container[field] = datetime.fromisoformat(
                    container[field].replace("Z", "+00:00")
                ).timestamp()

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(error["loc"] == expected_location for error in raised.exception.errors())
                )

    def test_rejects_unix_timestamp_strings(self):
        for target in ("departure", "arrival", "occurrence"):
            with self.subTest(target=target):
                payload = make_trip_context_payload()

                if target == "occurrence":
                    container = payload["stop_occurrences"][0]
                    field = "planned_arrival_at"
                    expected_location = ("stop_occurrences", 0, field)
                else:
                    container = payload
                    field = (
                        "planned_departure_at" if target == "departure" else "planned_arrival_at"
                    )
                    expected_location = (field,)

                container[field] = str(
                    datetime.fromisoformat(container[field].replace("Z", "+00:00")).timestamp()
                )

                with self.assertRaises(ValidationError) as raised:
                    TripContext.model_validate(payload)

                self.assertTrue(
                    any(error["loc"] == expected_location for error in raised.exception.errors())
                )


if __name__ == "__main__":
    unittest.main()
