"""Exercise the real terminal entry point with offline subprocesses."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_PATH = "examples/temperature_sample.csv"


class CosiCliTests(unittest.TestCase):
    """Check observable output and exit codes using the current interpreter."""

    def setUp(self) -> None:
        """Create an isolated directory for temporary input files."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.csv_path = Path(self.directory.name) / "measurements.csv"

    def run_cli(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        """Run cosi.py without a shell and capture both output streams."""
        return subprocess.run(
            [sys.executable, "cosi.py", *arguments],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )

    def test_sample_with_default_threshold(self) -> None:
        """The default threshold produces all agreed calibration results."""
        completed = self.run_cli([SAMPLE_PATH])

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        expected_lines = [
            r"Messwerte insgesamt:\s*6\b",
            r"Gültige Messwerte:\s*5\b",
            r"Fehlende Messwerte:\s*1\b",
            r"Minimum:\s*40\.0\s*°C",
            r"Maximum:\s*65\.0\s*°C",
            r"Arithmetischer Mittelwert:\s*53\.6\s*°C",
            r"Schwellenwert:\s*60\.0\s*°C",
            r"Werte strikt oberhalb des Schwellenwerts:\s*2\b",
        ]
        # Whitespace patterns allow harmless changes in report alignment.
        for pattern in expected_lines:
            with self.subTest(pattern=pattern):
                self.assertRegex(completed.stdout, pattern)

    def test_threshold_sixty_five_has_no_exceedances(self) -> None:
        """The CLI forwards the threshold, preserving strict comparison."""
        completed = self.run_cli([SAMPLE_PATH, "--threshold", "65"])

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        self.assertRegex(completed.stdout, r"Schwellenwert:\s*65\.0\s*°C")
        self.assertRegex(
            completed.stdout, r"Werte strikt oberhalb des Schwellenwerts:\s*0\b"
        )

    def test_help_succeeds_without_a_file(self) -> None:
        """Help explains the arguments in German and requires no CSV input."""
        completed = self.run_cli(["--help"])

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        self.assertIn("Temperaturmessungen", completed.stdout)
        self.assertIn("DATEI", completed.stdout)
        self.assertIn("--threshold", completed.stdout)
        self.assertIn("Standard: 60.0", completed.stdout)
        self.assertNotIn("Messwerte insgesamt:", completed.stdout)

    def test_missing_path_is_an_argument_error(self) -> None:
        """A required positional argument is enforced by argparse."""
        completed = self.run_cli([])

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("DATEI", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_invalid_thresholds_are_checked_before_the_file(self) -> None:
        """Invalid thresholds win over the deliberately nonexistent file."""
        for threshold in ("text", "True", "", "NaN", "inf", "-inf", "1e400"):
            with self.subTest(threshold=threshold):
                completed = self.run_cli([
                    str(self.csv_path), f"--threshold={threshold}"
                ])

                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn("endliche Zahl", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)

    def test_missing_option_value_and_unknown_option_are_argument_errors(self) -> None:
        """Malformed command lines fail before producing any statistics."""
        for arguments in ([SAMPLE_PATH, "--threshold"], [SAMPLE_PATH, "--unknown"]):
            with self.subTest(arguments=arguments):
                completed = self.run_cli(arguments)

                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertTrue(completed.stderr.strip())
                self.assertNotIn("Traceback", completed.stderr)

    def test_missing_file_is_a_runtime_error(self) -> None:
        """File errors produce an error message without a traceback or report."""
        completed = self.run_cli([str(self.csv_path)])

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("Fehler", completed.stderr)
        self.assertIn(self.csv_path.name, completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_invalid_csv_does_not_print_partial_results(self) -> None:
        """An error after a valid row prevents the entire report."""
        self.csv_path.write_text(
            "time_s,temperature_c\n0,40\n10,invalid\n", encoding="utf-8"
        )

        completed = self.run_cli([str(self.csv_path)])

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("Fehler", completed.stderr)
        self.assertIn("Line 3", completed.stderr)
        self.assertIn("temperature_c", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_only_missing_temperatures_are_an_analysis_error(self) -> None:
        """Valid CSV with no valid temperatures cannot produce statistics."""
        self.csv_path.write_text(
            "time_s,temperature_c\n0,\n10,   \n", encoding="utf-8"
        )

        completed = self.run_cli([str(self.csv_path)])

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("Fehler", completed.stderr)
        self.assertIn("valid measurement", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_output_does_not_add_rounding(self) -> None:
        """Display a precise input using its normal float representation."""
        self.csv_path.write_text(
            "time_s,temperature_c\n0,1.23456789\n", encoding="utf-8"
        )

        completed = self.run_cli([str(self.csv_path)])

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        self.assertRegex(
            completed.stdout, r"Arithmetischer Mittelwert:\s*1\.23456789\s*°C"
        )

    def test_import_does_not_start_cli(self) -> None:
        """Importing cosi must not parse arguments, read files, or print a report."""
        completed = subprocess.run(
            [sys.executable, "-c", "import cosi; print('import-ok')"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "import-ok")
        self.assertEqual(completed.stderr, "")
