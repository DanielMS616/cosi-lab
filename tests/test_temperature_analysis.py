"""Offline examples of the public temperature-analysis contract."""

import unittest

from temperature_analysis import analyze_temperatures


class TemperatureAnalysisTests(unittest.TestCase):
    """Check normal inputs, threshold boundaries, missing data, and errors."""

    def test_reference_example(self) -> None:
        """Verify every result in the agreed calibration example."""
        values = [40, 42, None, 61, 65, 60]

        result = analyze_temperatures(values, threshold=60)

        self.assertEqual(
            set(result),
            {
                "total_count", "valid_count", "missing_count",
                "minimum", "maximum", "mean", "exceedance_count",
            },
        )
        self.assertEqual(result["total_count"], 6)
        self.assertEqual(result["valid_count"], 5)
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["minimum"], 40)
        self.assertEqual(result["maximum"], 65)
        self.assertAlmostEqual(result["mean"], 53.6)
        self.assertEqual(result["exceedance_count"], 2)
        self.assertEqual(values, [40, 42, None, 61, 65, 60])

    def test_exactly_sixty_is_not_an_exceedance(self) -> None:
        """A measurement equal to the default threshold must not count."""
        result = analyze_temperatures([60])

        self.assertEqual(result["exceedance_count"], 0)
        self.assertAlmostEqual(result["mean"], 60.0)

    def test_values_on_both_sides_of_default_threshold(self) -> None:
        """Only the value above 60 counts, even with a small difference."""
        result = analyze_temperatures([59.999, 60.0, 60.001])

        self.assertEqual(result["exceedance_count"], 1)
        self.assertEqual(result["missing_count"], 0)

    def test_missing_values_are_counted_without_replacement(self) -> None:
        """Missing measurements do not enter extrema or the mean's divisor."""
        result = analyze_temperatures([None, 20.0, None, 40.0, None])

        self.assertEqual(result["total_count"], 5)
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["missing_count"], 3)
        self.assertAlmostEqual(result["minimum"], 20.0)
        self.assertAlmostEqual(result["maximum"], 40.0)
        self.assertAlmostEqual(result["mean"], 30.0)
        self.assertEqual(result["exceedance_count"], 0)

    def test_negative_values_and_custom_threshold(self) -> None:
        """Negative temperatures and a finite custom threshold are valid."""
        result = analyze_temperatures([-10.5, -2.5, 0], threshold=-2.5)

        self.assertAlmostEqual(result["minimum"], -10.5)
        self.assertEqual(result["maximum"], 0)
        self.assertAlmostEqual(result["mean"], -13 / 3)
        self.assertEqual(result["exceedance_count"], 1)

    def test_mean_is_not_rounded_to_decimal_places(self) -> None:
        """Retain floating-point precision beyond typical display rounding."""
        result = analyze_temperatures([0, 0, 1])

        self.assertAlmostEqual(result["mean"], 1 / 3, places=15)

    def test_unrepresentable_mean_raises_value_error(self) -> None:
        """Translate mean overflow while preserving the original error as cause."""
        values = [10**400, 10**400 + 1]

        with self.assertRaisesRegex(ValueError, "mean cannot be represented") as caught:
            analyze_temperatures(values)

        self.assertIsInstance(caught.exception.__cause__, OverflowError)

    def test_only_missing_values_raise_value_error(self) -> None:
        """A nonempty list can still contain no usable measurements."""
        with self.assertRaises(ValueError):
            analyze_temperatures([None, None])

    def test_empty_list_raises_value_error(self) -> None:
        """No statistics can be calculated without measurements."""
        with self.assertRaises(ValueError):
            analyze_temperatures([])

    def test_invalid_measurements_raise_value_error(self) -> None:
        """Reject invalid entries even when valid measurements are present."""
        invalid_values = [
            "60", "invalid", True, False, float("nan"),
            float("inf"), float("-inf"), 1 + 2j, [], {},
        ]

        # Each subtest identifies the failing input while allowing the other
        # cases to run. None is deliberately absent: it means missing data.
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    analyze_temperatures([40, value, 65])

    def test_invalid_thresholds_raise_value_error(self) -> None:
        """The threshold cannot be missing, nonnumeric, boolean, or nonfinite."""
        invalid_thresholds = [
            None, "60", True, False, float("nan"),
            float("inf"), float("-inf"), 1 + 2j, [], {},
        ]

        for threshold in invalid_thresholds:
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValueError):
                    analyze_temperatures([40, 65], threshold=threshold)

    def test_values_must_be_a_list(self) -> None:
        """Reject containers outside the declared list input contract."""
        for values in (None, "40", 40, (40, 65), {40, 65}, {"value": 40}):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    analyze_temperatures(values)
