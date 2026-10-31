"""Test CSV validation and its integration with the temperature analysis."""

import tempfile
import unittest
from pathlib import Path

from temperature_analysis import analyze_temperatures
from temperature_csv import read_temperature_csv


SAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples/temperature_sample.csv"
HEADER = "time_s,temperature_c\n"


class TemperatureCsvTests(unittest.TestCase):
    """Use real temporary files to check parsing without external services."""

    def setUp(self) -> None:
        """Give each test its own directory and register automatic cleanup."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.csv_path = Path(self.directory.name) / "temperatures.csv"

    def write_csv(self, content: str) -> Path:
        """Write an exact UTF-8 fixture, preserving its supplied line endings."""
        self.csv_path.write_bytes(content.encode("utf-8"))
        return self.csv_path

    def test_sample_accepts_path_and_string(self) -> None:
        """Import every sample row with floats and an unchanged missing value."""
        expected_temperatures = [40.0, 42.0, None, 61.0, 65.0, 60.0]
        for path in (SAMPLE_PATH, str(SAMPLE_PATH)):
            with self.subTest(path=path):
                records = read_temperature_csv(path)

                self.assertEqual(len(records), 6)
                for index, record in enumerate(records):
                    self.assertEqual(set(record), {"time_s", "temperature_c"})
                    self.assertIsInstance(record["time_s"], float)
                    self.assertAlmostEqual(record["time_s"], index * 10.0)
                    expected = expected_temperatures[index]
                    if expected is None:
                        self.assertIsNone(record["temperature_c"])
                    else:
                        self.assertIsInstance(record["temperature_c"], float)
                        self.assertAlmostEqual(record["temperature_c"], expected)

    def test_sample_analysis_integration(self) -> None:
        """Pass imported temperatures to the unchanged calculation component."""
        records = read_temperature_csv(SAMPLE_PATH)
        temperatures = [record["temperature_c"] for record in records]

        result = analyze_temperatures(temperatures, threshold=60)

        self.assertEqual(result["total_count"], 6)
        self.assertEqual(result["valid_count"], 5)
        self.assertEqual(result["missing_count"], 1)
        self.assertAlmostEqual(result["minimum"], 40.0)
        self.assertAlmostEqual(result["maximum"], 65.0)
        self.assertAlmostEqual(result["mean"], 53.6)
        self.assertEqual(result["exceedance_count"], 2)

    def test_only_missing_temperatures_import_but_cannot_be_analyzed(self) -> None:
        """Valid timestamps survive import even when no temperature is usable."""
        path = self.write_csv(HEADER + "0,\n10,   \n20,\t\n")

        records = read_temperature_csv(path)

        self.assertEqual(len(records), 3)
        for index, record in enumerate(records):
            self.assertAlmostEqual(record["time_s"], index * 10.0)
            self.assertIsNone(record["temperature_c"])
        temperatures = [record["temperature_c"] for record in records]
        with self.assertRaises(ValueError):
            analyze_temperatures(temperatures)

    def test_decimal_negative_values_and_crlf(self) -> None:
        """Accept finite decimals and CRLF without requiring a final newline."""
        path = self.write_csv("time_s,temperature_c\r\n-1.5,-2.25\r\n0.5,1e2")

        records = read_temperature_csv(path)

        self.assertAlmostEqual(records[0]["time_s"], -1.5)
        self.assertAlmostEqual(records[0]["temperature_c"], -2.25)
        self.assertAlmostEqual(records[1]["time_s"], 0.5)
        self.assertAlmostEqual(records[1]["temperature_c"], 100.0)

    def test_empty_file_and_header_only_are_errors(self) -> None:
        """Require both the header and at least one data row."""
        for content, expected_line in (("", 1), (HEADER, 2), (HEADER.rstrip(), 2)):
            with self.subTest(content=content):
                path = self.write_csv(content)
                with self.assertRaisesRegex(ValueError, f"Line {expected_line}:"):
                    read_temperature_csv(path)

    def test_wrong_headers_are_errors(self) -> None:
        """Reject missing, renamed, reordered, or extra column names."""
        headers = [
            "\n", "time_s\n", "temperature_c,time_s\n",
            "time_s,temperature\n", "time_s, temperature_c\n",
            "time_s,temperature_c,extra\n", "time_s;temperature_c\n",
        ]
        for header in headers:
            with self.subTest(header=header):
                path = self.write_csv(header + "0,40\n")
                with self.assertRaisesRegex(ValueError, "Line 1:.*header"):
                    read_temperature_csv(path)

    def test_wrong_field_counts_are_errors(self) -> None:
        """Reject short and long records after a valid row, without skipping."""
        for row in ("10", "10,42,extra", "10,42,"):
            with self.subTest(row=row):
                path = self.write_csv(HEADER + "0,40\n" + row + "\n20,65\n")
                with self.assertRaisesRegex(ValueError, "Line 3:.*two fields"):
                    read_temperature_csv(path)

    def test_empty_data_rows_are_errors(self) -> None:
        """Blank lines and wholly blank records must never disappear silently."""
        for row in ("", "   ", ",", " , \t"):
            with self.subTest(row=row):
                path = self.write_csv(HEADER + "0,40\n" + row + "\n20,65\n")
                with self.assertRaisesRegex(ValueError, "Line 3:.*empty data row"):
                    read_temperature_csv(path)

    def test_invalid_timestamps_are_errors(self) -> None:
        """Report missing, nonnumeric, and nonfinite timestamps with their field."""
        for value in ("", "   ", "text", "NaN", "inf", "-Infinity", "1e400"):
            with self.subTest(value=value):
                path = self.write_csv(HEADER + f"{value},40\n")
                with self.assertRaisesRegex(ValueError, "Line 2, field time_s:"):
                    read_temperature_csv(path)

    def test_duplicate_and_decreasing_timestamps_are_errors(self) -> None:
        """Strict ordering excludes equal timestamps, including numeric aliases."""
        for time_s in ("10", "10.0", "9"):
            with self.subTest(time_s=time_s):
                path = self.write_csv(HEADER + "10,40\n" + f"{time_s},42\n")
                with self.assertRaisesRegex(
                    ValueError, "Line 3, field time_s:.*strictly increasing"
                ):
                    read_temperature_csv(path)

    def test_invalid_temperatures_are_errors(self) -> None:
        """Report invalid temperatures rather than replacing them with None."""
        for value in ("text", "True", "NaN", "inf", "-Infinity", "1e400"):
            with self.subTest(value=value):
                path = self.write_csv(HEADER + "0,40\n" + f"10,{value}\n")
                with self.assertRaisesRegex(ValueError, "Line 3, field temperature_c:"):
                    read_temperature_csv(path)

    def test_malformed_csv_is_a_value_error(self) -> None:
        """Translate CSV quoting errors and retain the failing line number."""
        for row in ('10,"42', '10,"42"extra'):
            with self.subTest(row=row):
                path = self.write_csv(HEADER + "0,40\n" + row + "\n")
                with self.assertRaisesRegex(ValueError, "Line 3:.*CSV format"):
                    read_temperature_csv(path)

    def test_invalid_utf8_is_a_value_error(self) -> None:
        """Identify the physical line containing an invalid UTF-8 byte."""
        self.csv_path.write_bytes((HEADER + "0,40\n").encode("utf-8") + b"10,\xff\n")

        with self.assertRaisesRegex(ValueError, "Line 3:.*UTF-8"):
            read_temperature_csv(self.csv_path)

    def test_missing_file_error_propagates(self) -> None:
        """A missing file remains a file-system error, not a format error."""
        with self.assertRaises(FileNotFoundError):
            read_temperature_csv(self.csv_path)
