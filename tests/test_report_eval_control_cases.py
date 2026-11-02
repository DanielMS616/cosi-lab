"""Check the fixed prompt-comparison control data offline through import and analysis."""

import json
import unittest
from pathlib import Path

from temperature_analysis import analyze_temperatures
from temperature_csv import read_temperature_csv


MANIFEST_PATH = Path(__file__).resolve().parent.parent / "examples/report_eval/control_cases.json"
RESULT_FIELDS = {
    "total_count", "valid_count", "missing_count",
    "minimum", "maximum", "mean", "exceedance_count",
}


class ReportEvalControlCasesTests(unittest.TestCase):
    """Compare both real control CSV files with independently specified expectations."""

    def test_control_cases_match_manifest(self) -> None:
        """Verify every statistic using literal manifest facts, without generating text."""
        cases = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(cases, list)
        self.assertEqual(len(cases), 2)
        self.assertEqual({case["case_id"] for case in cases}, {
            "all_above", "repeated_threshold",
        })

        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                self.assertEqual(set(case), {"case_id", "csv_file", "threshold", "expected_result"})
                relative_path = Path(case["csv_file"])
                self.assertFalse(relative_path.is_absolute())
                records = read_temperature_csv(MANIFEST_PATH.parent / relative_path)
                self.assertEqual([record["time_s"] for record in records],
                                 list(range(0, len(records) * 10, 10)))
                temperatures = [record["temperature_c"] for record in records]
                result = analyze_temperatures(temperatures, threshold=case["threshold"])

                # Keep the supplied expectations independent of the analysis under test.
                expected = case["expected_result"]
                self.assertEqual(set(expected), RESULT_FIELDS)
                self.assertEqual(set(result), RESULT_FIELDS)
                for field in sorted(RESULT_FIELDS):
                    with self.subTest(field=field):
                        if field == "mean":
                            self.assertAlmostEqual(result[field], expected[field])
                        else:
                            self.assertEqual(result[field], expected[field])
