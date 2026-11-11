"""Deterministic batch estimates against a resolved Trip plan."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.schemas.batch_arrivals_schema import BatchArrivalsRequest
from app.schemas.trip_context_schema import TripContext
from app.services.batch_arrivals import (
    BatchInputError,
    TripNotEstimable,
    calculate_batch_arrivals,
)
from tests.support.arrivals import (
    make_arrivals_payload,
    make_arrivals_plan,
    make_confirmed_arrival_payload,
)


CALCULATED_AT = datetime(2026, 10, 21, 15, 5, tzinfo=timezone.utc)


class BatchArrivalsTests(unittest.TestCase):
    def calculate(self, payload=None, plan=None):
        return calculate_batch_arrivals(
            BatchArrivalsRequest.model_validate(
                make_arrivals_payload() if payload is None else payload
            ),
            TripContext.model_validate(make_arrivals_plan() if plan is None else plan),
            calculated_at=CALCULATED_AT,
        ).model_dump(mode="json")

    def test_calculates_ordered_estimates_for_repeated_stop_visits(self):
        payload = make_arrivals_payload()
        payload["observed_at"] = "2026-10-21T09:04:59.750-06:00"
        result = self.calculate(payload)

        self.assertEqual(result["trip_id"], make_arrivals_plan()["trip_id"])
        self.assertEqual(result["route_revision"], payload["route_revision"])
        self.assertEqual(result["position_version"], 12)
        self.assertEqual(result["observed_at"], "2026-10-21T15:04:59.750000Z")
        self.assertEqual(result["calculated_at"], "2026-10-21T15:05:00Z")
        self.assertEqual(result["source_age_seconds"], 0.25)
        first, second = result["arrivals"]
        self.assertEqual(first["stop_id"], second["stop_id"])
        self.assertEqual(
            [item["stop_occurrence_id"] for item in result["arrivals"]],
            [target["stop_occurrence_id"] for target in payload["targets"]],
        )
        self.assertEqual([first["stop_sequence"], second["stop_sequence"]], [1, 2])
        self.assertEqual([first["eta_seconds"], second["eta_seconds"]], [100, 250])
        self.assertEqual(first["arrival_at"], "2026-10-21T15:06:40Z")
        self.assertEqual(second["arrival_at"], "2026-10-21T15:09:10Z")
        self.assertEqual(second["planned_arrival_at"], "2026-10-21T15:30:00Z")
        self.assertEqual(second["method"], "distance_speed")
        self.assertEqual(second["quality_reason"], "current_speed")
        self.assertIsNone(second["model_version"])
        self.assertNotIn("confidence", second)

    def test_rounds_up_and_accepts_one_meter_of_distance_tolerance(self):
        payload = make_arrivals_payload()
        payload["targets"][0]["remaining_distance_m"] = 1001.0

        result = self.calculate(payload)

        self.assertEqual(result["arrivals"][0]["eta_seconds"], 101)
        self.assertEqual(result["arrivals"][0]["remaining_distance_m"], 1001.0)

    def test_rejects_invalid_targets_with_the_exact_field_path(self):
        cases = {
            "duplicate": ("targets", 1, "stop_occurrence_id"),
            "unknown": ("targets", 0, "stop_occurrence_id"),
            "out of order": ("targets", 1, "stop_occurrence_id"),
            "passed": ("targets", 0, "stop_occurrence_id"),
            "distance mismatch": ("targets", 0, "remaining_distance_m"),
            "outside route": ("tracking", "distance_along_route_m"),
            "confirmation missing from targets": ("tracking", "confirmed_stop_occurrence_id"),
            "confirmation with nonzero distance": ("targets", 0, "remaining_distance_m"),
        }
        for scenario, path in cases.items():
            with self.subTest(scenario=scenario):
                payload = make_arrivals_payload()
                first, second = payload["targets"]
                if scenario == "duplicate":
                    second["stop_occurrence_id"] = first["stop_occurrence_id"]
                elif scenario == "unknown":
                    first["stop_occurrence_id"] = "99999999-9999-4999-8999-999999999999"
                elif scenario == "out of order":
                    payload["targets"].reverse()
                elif scenario == "passed":
                    payload["tracking"]["distance_along_route_m"] = 1000.01
                elif scenario == "distance mismatch":
                    first["remaining_distance_m"] = 1001.01
                elif scenario == "outside route":
                    payload["tracking"]["distance_along_route_m"] = 3000.01
                elif scenario == "confirmation missing from targets":
                    payload["tracking"]["confirmed_stop_occurrence_id"] = first[
                        "stop_occurrence_id"
                    ]
                    payload["targets"] = [second]
                else:
                    payload["tracking"]["confirmed_stop_occurrence_id"] = first[
                        "stop_occurrence_id"
                    ]
                    payload["tracking"]["distance_along_route_m"] = 1000.0
                    first["remaining_distance_m"] = 1.0
                with self.assertRaises(BatchInputError) as error:
                    self.calculate(payload)
                self.assertEqual(error.exception.path, path)

    def test_checks_future_skew_with_fractional_precision(self):
        payload = make_arrivals_payload()
        payload["observed_at"] = "2026-10-21T15:05:05Z"
        self.assertEqual(self.calculate(payload)["source_age_seconds"], 0.0)

        payload["observed_at"] = "2026-10-21T15:05:05.000001Z"
        with self.assertRaises(BatchInputError) as error:
            self.calculate(payload)
        self.assertEqual(error.exception.path, ("observed_at",))

    def test_validates_the_whole_batch_before_calculating_any_target(self):
        payload = make_arrivals_payload()
        payload["targets"][1]["remaining_distance_m"] = 0.0

        with patch("app.services.batch_arrivals.calculate_fallback_eta") as calculate:
            with self.assertRaises(BatchInputError):
                self.calculate(payload)
            calculate.assert_not_called()

    def test_limits_live_estimates_to_usable_moving_observations(self):
        cases = (
            ({"on_route": False}, "off_route"),
            ({"accuracy_meters": None}, "poor_accuracy"),
            ({"current_speed_kmh": 0}, "no_usable_speed"),
        )
        for tracking, reason in cases:
            with self.subTest(tracking=tracking):
                payload = make_arrivals_payload()
                payload["tracking"].update(tracking)
                arrival = self.calculate(payload)["arrivals"][0]
                self.assertEqual(arrival["method"], "scheduled_reference")
                self.assertEqual(arrival["quality_reason"], reason)
                self.assertIsNone(arrival["arrival_at"])
                self.assertIsNone(arrival["eta_seconds"])
                self.assertEqual(arrival["planned_arrival_at"], "2026-10-21T15:00:00Z")

    def test_stale_observations_and_unconfirmed_zero_distance_return_no_live_eta(self):
        payload = make_arrivals_payload()
        payload["observed_at"] = "2026-10-21T15:04:30Z"
        self.assertEqual(self.calculate(payload)["arrivals"][0]["eta_seconds"], 100)

        payload["observed_at"] = "2026-10-21T15:04:29.999999Z"
        self.assertEqual(self.calculate(payload)["arrivals"][0]["quality_reason"], "stale_observation")

        payload["observed_at"] = "2026-10-21T15:05:00Z"
        payload["tracking"]["distance_along_route_m"] = 1000.0
        payload["targets"][0]["remaining_distance_m"] = 0.0
        payload["targets"][1]["remaining_distance_m"] = 1500.0
        arrivals = self.calculate(payload)["arrivals"]
        self.assertIsNone(arrivals[0]["eta_seconds"])
        self.assertEqual(arrivals[0]["quality_reason"], "arrival_unconfirmed")
        self.assertEqual(arrivals[1]["eta_seconds"], 150)

    def test_marks_only_the_confirmed_occurrence_arrived_at_its_observation_time(self):
        cases = (
            ("2026-10-21T15:04:57.250000Z", "2026-10-21T15:04:57.250000Z"),
            ("2026-10-21T15:05:05Z", "2026-10-21T15:05:00Z"),
        )
        for observed_at, arrival_at in cases:
            with self.subTest(observed_at=observed_at):
                payload = make_confirmed_arrival_payload()
                payload["observed_at"] = observed_at

                result = self.calculate(payload)
                confirmed, upcoming = result["arrivals"]

                self.assertEqual(result["observed_at"], observed_at)
                self.assertEqual(confirmed["stop_id"], upcoming["stop_id"])
                self.assertEqual(confirmed["eta_seconds"], 0)
                self.assertEqual(confirmed["arrival_at"], arrival_at)
                self.assertEqual(confirmed["method"], "arrived")
                self.assertEqual(confirmed["quality_reason"], "confirmed_arrival")
                self.assertEqual(confirmed["planned_arrival_at"], "2026-10-21T15:00:00Z")
                self.assertIsNone(upcoming["eta_seconds"])
                self.assertIsNone(upcoming["arrival_at"])
                self.assertEqual(upcoming["quality_reason"], "no_usable_speed")

    def test_observation_quality_and_trip_state_take_precedence_over_confirmation(self):
        cases = (
            ("scheduled", "2026-10-21T15:04:00Z", False, None, "trip_not_started"),
            ("in_progress", "2026-10-21T15:04:00Z", False, None, "stale_observation"),
            ("in_progress", "2026-10-21T15:05:00Z", False, None, "off_route"),
            ("in_progress", "2026-10-21T15:05:00Z", True, None, "poor_accuracy"),
        )
        for status, observed_at, on_route, accuracy, reason in cases:
            with self.subTest(reason=reason):
                plan = make_arrivals_plan()
                plan["status"] = status
                payload = make_confirmed_arrival_payload()
                payload["observed_at"] = observed_at
                payload["tracking"].update(on_route=on_route, accuracy_meters=accuracy)

                result = self.calculate(payload, plan)
                confirmed = result["arrivals"][0]

                self.assertEqual(confirmed["method"], "scheduled_reference")
                self.assertEqual(confirmed["quality_reason"], reason)
                self.assertIsNone(confirmed["eta_seconds"])
                self.assertIsNone(confirmed["arrival_at"])

    def test_scheduled_and_terminal_trips_cannot_produce_live_estimates(self):
        plan = make_arrivals_plan()
        plan["status"] = "scheduled"
        plan["stop_occurrences"][0]["planned_arrival_at"] = None
        arrival = self.calculate(plan=plan)["arrivals"][0]
        self.assertEqual(arrival["method"], "unavailable")
        self.assertEqual(arrival["quality_reason"], "trip_not_started")

        for status in ("completed", "cancelled"):
            with self.subTest(status=status):
                plan["status"] = status
                with self.assertRaises(TripNotEstimable):
                    self.calculate(plan=plan)

    def test_extreme_positive_speed_calculation_cannot_overflow_the_response(self):
        payload = make_arrivals_payload()
        payload["tracking"]["current_speed_kmh"] = 1e-100
        arrival = self.calculate(payload)["arrivals"][0]
        self.assertIsNone(arrival["eta_seconds"])
        self.assertIsNone(arrival["arrival_at"])
        self.assertEqual(arrival["method"], "unavailable")
        self.assertEqual(arrival["quality_reason"], "calculation_unavailable")
