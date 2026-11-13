"""Tests for the incoming versioned batch arrival contract."""

import unittest

from pydantic import ValidationError

from app.schemas.batch_arrivals_schema import BatchArrivalsRequest
from tests.support.arrivals import make_arrivals_payload


class BatchArrivalsSchemaTests(unittest.TestCase):
    def test_normalizes_aware_instants_and_accepts_unknown_current_speed(self):
        payload = make_arrivals_payload()
        payload["observed_at"] = "2026-10-21T09:05:00-06:00"
        payload["tracking"].update(
            current_speed_kmh=None,
            effective_speed_kmh=24,
            effective_speed_observed_at="2026-10-21T09:04:55-06:00",
        )

        parsed = BatchArrivalsRequest.model_validate(payload).model_dump(mode="json")

        self.assertEqual(parsed["observed_at"], "2026-10-21T15:05:00Z")
        self.assertEqual(parsed["tracking"]["effective_speed_observed_at"], "2026-10-21T15:04:55Z")
        self.assertIsNone(parsed["tracking"]["current_speed_kmh"])

    def test_rejects_coercion_and_invalid_values_at_the_input_field(self):
        cases = (
            (("contract_version",), True),
            (("contract_version",), 2),
            (("route_revision",), "A" * 64),
            (("position_version",), "12"),
            (("position_version",), 0),
            (("observed_at",), 1792595100),
            (("observed_at",), "1792595100"),
            (("observed_at",), "2026-10-21T15:05:00"),
            (("observed_at",), "0001-01-01T00:00:00+01:00"),
            (("observed_at",), "9999-12-31T23:59:59-01:00"),
            (("tracking", "on_route"), 1),
            (("tracking", "accuracy_meters"), float("inf")),
            (("tracking", "current_speed_kmh"), -1),
            (("tracking", "current_speed_kmh"), 401),
            (("tracking", "distance_along_route_m"), True),
            (("targets", 0, "remaining_distance_m"), "1000"),
            (("targets", 0, "remaining_distance_m"), float("nan")),
            (("targets", 0, "remaining_distance_m"), -1),
            (("targets", 0, "stop_occurrence_id"), "unknown"),
        )
        for path, value in cases:
            with self.subTest(path=path, value=value):
                payload = make_arrivals_payload()
                target = payload
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                with self.assertRaises(ValidationError) as error:
                    BatchArrivalsRequest.model_validate(payload)
                self.assertEqual(error.exception.errors()[0]["loc"], path)

    def test_rejects_unsupported_nested_fields(self):
        payload = make_arrivals_payload()
        payload["targets"][0]["planned_arrival_at"] = "2026-10-21T15:30:00Z"

        with self.assertRaises(ValidationError) as error:
            BatchArrivalsRequest.model_validate(payload)
        self.assertEqual(error.exception.errors()[0]["loc"], ("targets", 0, "planned_arrival_at"))

    def test_requires_the_effective_speed_and_instant_to_be_present_together(self):
        for speed, observed_at in ((20, None), (None, "2026-10-21T15:04:55Z")):
            with self.subTest(speed=speed, observed_at=observed_at):
                payload = make_arrivals_payload()
                payload["tracking"].update(
                    effective_speed_kmh=speed,
                    effective_speed_observed_at=observed_at,
                )
                with self.assertRaises(ValidationError) as error:
                    BatchArrivalsRequest.model_validate(payload)
                self.assertEqual(
                    error.exception.errors()[0]["loc"],
                    ("tracking", "effective_speed_observed_at"),
                )

    def test_limits_target_count_to_one_through_one_hundred(self):
        for count in (0, 101):
            with self.subTest(count=count):
                payload = make_arrivals_payload()
                payload["targets"] = payload["targets"][:1] * count
                with self.assertRaises(ValidationError) as error:
                    BatchArrivalsRequest.model_validate(payload)
                self.assertEqual(error.exception.errors()[0]["loc"], ("targets",))
