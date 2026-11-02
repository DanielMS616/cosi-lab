"""Check the terminal entry point and model-report integration entirely offline."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import cosi
from openai_text import OpenAITextError


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
        self.assertIn("--model-report", completed.stdout)
        self.assertIn("--model", completed.stdout)
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


class CosiModelReportTests(unittest.TestCase):
    """Keep import, analysis, prompts, and logs real; replace the text generator."""

    def setUp(self) -> None:
        """Supply fixed model text and block HTTP independently as a test safeguard."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.sample = str(PROJECT_DIR / SAMPLE_PATH)
        self.fixed_report = "Fester Modellbericht ohne Qualitätsnachweis."
        generator = patch("cosi.generate_text", return_value=self.fixed_report)
        self.generator = generator.start()
        self.addCleanup(generator.stop)
        http_boundary = patch(
            "openai_text.http.client.HTTPSConnection",
            side_effect=AssertionError("These CLI tests must never use HTTP."),
        )
        self.http_boundary = http_boundary.start()
        self.addCleanup(http_boundary.stop)

    def call_main(self, arguments: list[str]) -> tuple[int, str, str]:
        """Capture CLI streams and argparse exits while allowing generator injection."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = cosi.main(arguments)
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue()

    def read_events(self, log_dir: Path) -> list[dict]:
        """Read the one real log produced by a CLI invocation."""
        paths = list(log_dir.glob("*.jsonl"))
        self.assertEqual(len(paths), 1)
        return [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines()]

    def test_standard_call_never_calls_generator(self) -> None:
        """The default remains offline, with or without logging."""
        for logging in (False, True):
            with self.subTest(logging=logging):
                log_dir = self.root / "offline-logs"
                arguments = [self.sample]
                if logging:
                    arguments += ["--log-dir", str(log_dir)]
                code, stdout, stderr = self.call_main(arguments)
                self.assertEqual(code, 0)
                self.assertEqual(stderr, "")
                self.assertIn("Messwerte insgesamt: 6", stdout)
                self.assertNotIn("Modellbericht", stdout)
                self.generator.assert_not_called()
                self.http_boundary.assert_not_called()
                if logging:
                    self.assertEqual(len(self.read_events(log_dir)), 6)

    def test_model_and_same_validated_threshold_reach_report(self) -> None:
        """Inspect the real prompt to prove analysis and report use the same threshold."""
        cases = [([], "gpt-4.1-mini", 60.0, 2),
                 (["--model", "test-model", "--threshold", "65"], "test-model", 65.0, 0)]
        for options, model, threshold, exceedances in cases:
            with self.subTest(model=model, threshold=threshold):
                self.generator.reset_mock()
                code, stdout, stderr = self.call_main([self.sample, "--model-report", *options])
                self.assertEqual(code, 0)
                self.assertEqual(stderr, "")
                self.generator.assert_called_once()
                self.assertEqual(self.generator.call_args.kwargs, {"model": model})
                prompt = self.generator.call_args.args[0]
                facts = json.loads(prompt.split("Kennzahlen (JSON):\n", 1)[1])
                self.assertEqual(facts, {
                    "total_count": 6, "valid_count": 5, "missing_count": 1,
                    "minimum": 40.0, "maximum": 65.0, "mean": 53.6,
                    "exceedance_count": exceedances, "threshold": threshold,
                })
                self.assertIn(f"Schwellenwert: {threshold} °C", stdout)
                self.assertIn(f"Werte strikt oberhalb des Schwellenwerts: {exceedances}", stdout)
                self.assertTrue(stdout.endswith("Modellbericht:\n" + self.fixed_report + "\n"))
                self.assertLess(stdout.index("Messwerte insgesamt:"), stdout.index("Modellbericht:"))
                self.http_boundary.assert_not_called()

    def test_invalid_model_arguments_stop_before_processing(self) -> None:
        """Argument failures cannot read input, request a report, or create logs."""
        cases = [
            ["--model", "test-model"],
            ["--model-report", "--model", ""],
            ["--model-report", "--model", " \t"],
            ["--model-report", "--model"],
            ["--model-report", "--threshold", "NaN"],
        ]
        log_dir = self.root / "argument-logs"
        with patch("cosi.read_temperature_csv") as importer:
            for options in cases:
                with self.subTest(options=options):
                    code, stdout, stderr = self.call_main([
                        self.sample, "--log-dir", str(log_dir), *options,
                    ])
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout, "")
                    self.assertTrue(stderr.strip())
                    self.assertNotIn("Traceback", stderr)
                    importer.assert_not_called()
                    self.generator.assert_not_called()
                    self.http_boundary.assert_not_called()
                    self.assertFalse(log_dir.exists())

    def test_help_does_not_start_processing(self) -> None:
        """Help remains successful even when report and log options are present."""
        log_dir = self.root / "help-logs"
        code, stdout, stderr = self.call_main([
            "--model-report", "--log-dir", str(log_dir), "--help",
        ])
        self.assertEqual(code, 0)
        self.assertIn("--model-report", stdout)
        self.assertEqual(stderr, "")
        self.generator.assert_not_called()
        self.http_boundary.assert_not_called()
        self.assertFalse(log_dir.exists())

    def test_processing_errors_do_not_start_model_report(self) -> None:
        """Import and analysis failures stop the run before the generator boundary."""
        for name, csv in (("import", "wrong,header\n"),
                          ("analysis", "time_s,temperature_c\n0,\n")):
            with self.subTest(step=name):
                path = self.root / f"{name}.csv"
                path.write_text(csv, encoding="utf-8")
                log_dir = self.root / name
                code, stdout, stderr = self.call_main([
                    str(path), "--model-report", "--log-dir", str(log_dir),
                ])
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertIn("Fehler", stderr)
                self.generator.assert_not_called()
                events = self.read_events(log_dir)
                self.assertNotIn("model_report", [event["step"] for event in events])
                self.assertEqual(events[-1]["status"], "error")

    def test_model_error_suppresses_all_output_and_logs_original_type(self) -> None:
        """A provider error becomes CLI code 1 and two error completion events."""
        self.generator.side_effect = OpenAITextError("Simulierter Modellfehler.")
        for logging in (False, True):
            with self.subTest(logging=logging):
                self.generator.reset_mock()
                log_dir = self.root / "model-error"
                arguments = [self.sample, "--model-report"]
                if logging:
                    arguments += ["--log-dir", str(log_dir)]
                code, stdout, stderr = self.call_main(arguments)
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertIn("Simulierter Modellfehler.", stderr)
                self.assertNotIn("Traceback", stderr)
                self.generator.assert_called_once()
                if logging:
                    events = self.read_events(log_dir)
                    self.assertEqual(len(events), 8)
                    self.assertEqual(
                        [(event["event"], event["step"], event["status"], event["error_type"])
                         for event in events[-3:]],
                        [("step_started", "model_report", "started", None),
                         ("step_finished", "model_report", "error", "OpenAITextError"),
                         ("run_finished", None, "error", "OpenAITextError")],
                    )
                    self.assertNotIn("Simulierter Modellfehler", json.dumps(events))

    def test_invalid_generator_response_is_report_failure(self) -> None:
        """The existing report interface still validates text before CLI output."""
        self.generator.return_value = " \t"
        log_dir = self.root / "invalid-text"
        code, stdout, stderr = self.call_main([
            self.sample, "--model-report", "--log-dir", str(log_dir),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Fehler", stderr)
        self.generator.assert_called_once()
        events = self.read_events(log_dir)
        self.assertEqual(events[-2]["step"], "model_report")
        for event in events[-2:]:
            self.assertEqual(event["status"], "error")
            self.assertEqual(event["error_type"], "ValueError")

    def test_successful_model_report_events_preserve_schema(self) -> None:
        """A report adds exactly one step and no prompt, model name, or generated text."""
        log_dir = self.root / "success"
        code, stdout, stderr = self.call_main([
            self.sample, "--model-report", "--log-dir", str(log_dir),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn(self.fixed_report, stdout)
        self.generator.assert_called_once()
        events = self.read_events(log_dir)
        self.assertEqual(
            [(event["event"], event["step"], event["status"]) for event in events],
            [("run_started", None, "started"),
             ("step_started", "csv_import", "started"),
             ("step_finished", "csv_import", "success"),
             ("step_started", "temperature_analysis", "started"),
             ("step_finished", "temperature_analysis", "success"),
             ("step_started", "model_report", "started"),
             ("step_finished", "model_report", "success"),
             ("run_finished", None, "success")],
        )
        for event in events:
            self.assertEqual(set(event), {
                "schema_version", "run_id", "timestamp", "event", "step",
                "status", "duration_ms", "error_type",
            })
            self.assertEqual(event["schema_version"], 1)
            self.assertIsNone(event["error_type"])
        self.assertEqual(len({event["run_id"] for event in events}), 1)
        self.assertNotIn(self.fixed_report, json.dumps(events))
