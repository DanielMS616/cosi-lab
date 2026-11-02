"""Check real JSONL runs and simulate failures at the log-file boundary."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import cosi
from openai_text import OpenAITextError
from run_logging import RunLoggingError, log_run, log_step


PROJECT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_PATH = PROJECT_DIR / "examples/temperature_sample.csv"
EVENT_FIELDS = {
    "schema_version", "run_id", "timestamp", "event", "step", "status",
    "duration_ms", "error_type",
}
SUCCESS_SEQUENCE = [
    ("run_started", None, "started"),
    ("step_started", "csv_import", "started"),
    ("step_finished", "csv_import", "success"),
    ("step_started", "temperature_analysis", "started"),
    ("step_finished", "temperature_analysis", "success"),
    ("run_finished", None, "success"),
]


class RunLoggingTests(unittest.TestCase):
    """Use temporary directories for logs and real CLI integration checks."""

    def setUp(self) -> None:
        """Keep every test's inputs and logs separate and remove them afterwards."""
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.log_dir = self.root / "logs"
        self.input_path = self.root / "input.csv"
        # Model-enabled integration tests use a fixed answer, never a real API.
        generator = patch("cosi.generate_text", return_value="Fester Modellbericht.")
        self.generator = generator.start()
        self.addCleanup(generator.stop)

    def run_cli(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        """Run the actual CLI in an isolated working directory."""
        return subprocess.run(
            [sys.executable, str(PROJECT_DIR / "cosi.py"), *arguments],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )

    def call_main(self, arguments: list[str]) -> tuple[int, str, str]:
        """Capture main directly so file-boundary failures can be injected."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cosi.main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def read_events(self, path: Path) -> list[dict]:
        """Verify complete JSON lines, common metadata, and the fixed schema."""
        content = path.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("\n"))
        events = [json.loads(line) for line in content.splitlines()]
        self.assertTrue(events)
        self.assertEqual(UUID(path.stem).version, 4)
        for event in events:
            self.assertEqual(set(event), EVENT_FIELDS)
            self.assertEqual(event["schema_version"], 1)
            self.assertEqual(event["run_id"], path.stem)
            timestamp = datetime.fromisoformat(event["timestamp"])
            self.assertEqual(timestamp.utcoffset(), timedelta(0))
            if event["event"].endswith("_finished"):
                self.assertIsInstance(event["duration_ms"], (int, float))
                self.assertGreaterEqual(event["duration_ms"], 0)
            else:
                self.assertIsNone(event["duration_ms"])
            if event["status"] != "error":
                self.assertIsNone(event["error_type"])
        return events

    def test_successful_run_has_complete_metadata_and_order(self) -> None:
        """The sample produces six events and the same successful report."""
        completed = self.run_cli([str(SAMPLE_PATH), "--log-dir", str(self.log_dir)])

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        self.assertRegex(completed.stdout, r"Arithmetischer Mittelwert:\s*53\.6\s*°C")
        files = list(self.log_dir.glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        events = self.read_events(files[0])
        sequence = [(event["event"], event["step"], event["status"]) for event in events]
        self.assertEqual(sequence, SUCCESS_SEQUENCE)

    def test_import_error_stops_before_analysis(self) -> None:
        """A bad input logs its failed import, without recording the input text."""
        secret_text = "private-invalid-value"
        self.input_path.write_text(
            f"time_s,temperature_c\n0,{secret_text}\n", encoding="utf-8"
        )
        completed = self.run_cli([
            str(self.input_path), "--log-dir", str(self.log_dir)
        ])

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("Line 2", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        log_path = next(self.log_dir.glob("*.jsonl"))
        events = self.read_events(log_path)
        self.assertEqual(
            [(event["event"], event["step"], event["status"]) for event in events],
            SUCCESS_SEQUENCE[:2] + [
                ("step_finished", "csv_import", "error"),
                ("run_finished", None, "error"),
            ],
        )
        self.assertEqual([event["error_type"] for event in events], [None, None, "ValueError", "ValueError"])
        content = log_path.read_text(encoding="utf-8")
        self.assertNotIn(secret_text, content)
        self.assertNotIn(str(self.input_path), content)
        self.assertNotIn("expected a number", content)

    def test_missing_file_records_exception_class(self) -> None:
        """An expected file-system error is logged without its path or message."""
        completed = self.run_cli([
            str(self.input_path), "--log-dir", str(self.log_dir)
        ])

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("Fehler", completed.stderr)
        events = self.read_events(next(self.log_dir.glob("*.jsonl")))
        self.assertEqual(len(events), 4)
        self.assertEqual(events[-2]["error_type"], "FileNotFoundError")
        self.assertEqual(events[-1]["error_type"], "FileNotFoundError")

    def test_analysis_error_records_failed_step_and_run(self) -> None:
        """Missing temperatures import successfully, then fail during analysis."""
        self.input_path.write_text("time_s,temperature_c\n0,\n", encoding="utf-8")
        completed = self.run_cli([
            str(self.input_path), "--log-dir", str(self.log_dir)
        ])

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("valid measurement", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        events = self.read_events(next(self.log_dir.glob("*.jsonl")))
        self.assertEqual(
            [(event["event"], event["step"], event["status"]) for event in events],
            SUCCESS_SEQUENCE[:4] + [
                ("step_finished", "temperature_analysis", "error"),
                ("run_finished", None, "error"),
            ],
        )
        self.assertEqual(events[-2]["error_type"], "ValueError")
        self.assertEqual(events[-1]["error_type"], "ValueError")

    def test_two_runs_create_distinct_files(self) -> None:
        """Each run has a new UUID and leaves the earlier file untouched."""
        arguments = [str(SAMPLE_PATH), "--log-dir", str(self.log_dir)]
        self.assertEqual(self.run_cli(arguments).returncode, 0)
        first_path = next(self.log_dir.glob("*.jsonl"))
        first_content = first_path.read_bytes()

        self.assertEqual(self.run_cli(arguments).returncode, 0)

        files = list(self.log_dir.glob("*.jsonl"))
        self.assertEqual(len(files), 2)
        self.assertEqual(first_path.read_bytes(), first_content)
        for path in files:
            self.read_events(path)

    def test_uuid_collision_does_not_overwrite(self) -> None:
        """Force a collision to verify exclusive creation, not just UUID luck."""
        fixed_id = UUID("dca85254-ce07-4cff-b80c-f9c1250e3880")
        self.log_dir.mkdir()
        existing = self.log_dir / f"{fixed_id}.jsonl"
        existing.write_text("existing content\n", encoding="utf-8")

        with patch("run_logging.uuid4", return_value=fixed_id):
            with self.assertRaises(RunLoggingError) as caught:
                with log_run(self.log_dir):
                    self.fail("A colliding log must not start processing.")

        self.assertIsInstance(caught.exception.__cause__, FileExistsError)
        self.assertEqual(existing.read_text(encoding="utf-8"), "existing content\n")

    def test_creation_failure_suppresses_report(self) -> None:
        """A regular file cannot serve as the log directory."""
        self.log_dir.write_text("not a directory", encoding="utf-8")
        completed = self.run_cli([str(SAMPLE_PATH), "--log-dir", str(self.log_dir)])

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout, "")
        self.assertIn("Protokollierung", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertEqual(self.log_dir.read_text(encoding="utf-8"), "not a directory")

    def test_write_failures_close_file_and_suppress_report(self) -> None:
        """Inject write errors at start, step completion, and run completion."""
        for failing_write in (1, 3, 6):
            with self.subTest(failing_write=failing_write):
                buffer = io.StringIO()
                stream = MagicMock(wraps=buffer)

                def write_or_fail(line: str) -> int:
                    """Model a device error on a selected write call."""
                    if stream.write.call_count == failing_write:
                        raise OSError("simulated write failure")
                    return buffer.write(line)

                stream.write.side_effect = write_or_fail
                # Only the logger's open is replaced; the real CSV importer runs.
                with patch("run_logging.open", return_value=stream, create=True):
                    code, stdout, stderr = self.call_main([
                        str(SAMPLE_PATH), "--log-dir", str(self.log_dir)
                    ])

                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertIn("Protokollierung", stderr)
                self.assertNotIn("Traceback", stderr)
                self.assertTrue(buffer.closed)
                stream.close.assert_called_once()
                self.assertEqual(stream.write.call_count, failing_write)

    def test_flush_failure_closes_file_and_suppresses_report(self) -> None:
        """Buffered I/O can fail on flush even if write appeared successful."""
        buffer = io.StringIO()
        stream = MagicMock(wraps=buffer)
        stream.flush.side_effect = OSError("simulated flush failure")
        with patch("run_logging.open", return_value=stream, create=True):
            code, stdout, stderr = self.call_main([
                str(SAMPLE_PATH), "--log-dir", str(self.log_dir)
            ])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Protokollierung", stderr)
        self.assertTrue(buffer.closed)

    def test_close_failure_suppresses_report(self) -> None:
        """A close error must prevent success even after run_finished was written."""
        buffer = io.StringIO()
        stream = MagicMock(wraps=buffer)

        def close_and_fail() -> None:
            """Model a file releasing its handle while reporting a close error."""
            buffer.close()
            raise OSError("simulated close failure")

        stream.close.side_effect = close_and_fail
        with patch("run_logging.open", return_value=stream, create=True):
            code, stdout, stderr = self.call_main([
                str(SAMPLE_PATH), "--model-report", "--log-dir", str(self.log_dir)
            ])

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("geschlossen", stderr)
        self.assertTrue(buffer.closed)
        self.assertEqual(stream.write.call_count, 8)
        self.generator.assert_called_once()

    def test_success_report_is_printed_after_close(self) -> None:
        """Observe the output boundary to enforce completion-before-reporting."""
        buffer = io.StringIO()
        stream = MagicMock(wraps=buffer)

        def print_after_close(*args, **kwargs) -> None:
            """Check the log state at the moment the CLI prints its report."""
            self.assertTrue(buffer.closed)
            last_event = json.loads(stream.write.call_args.args[0])
            self.assertEqual(last_event["event"], "run_finished")
            self.assertEqual(last_event["status"], "success")
            print(*args, **kwargs)

        with patch("run_logging.open", return_value=stream, create=True):
            with patch("cosi.print", side_effect=print_after_close, create=True):
                code, stdout, stderr = self.call_main([
                    str(SAMPLE_PATH), "--model-report", "--log-dir", str(self.log_dir)
                ])

        self.assertEqual(code, 0)
        self.assertIn("Messwerte insgesamt: 6", stdout)
        self.assertIn("Modellbericht:\nFester Modellbericht.", stdout)
        self.assertEqual(stderr, "")
        self.generator.assert_called_once()

    def test_model_step_logging_failures_stop_writing_and_suppress_output(self) -> None:
        """Write failures override report success or failure without further writes."""
        for model_fails, failing_write in ((False, 6), (False, 7), (False, 8),
                                          (True, 7), (True, 8)):
            with self.subTest(model_fails=model_fails, failing_write=failing_write):
                self.generator.reset_mock()
                self.generator.side_effect = (
                    OpenAITextError("Simulierter Modellfehler.") if model_fails else None
                )
                buffer = io.StringIO()
                stream = MagicMock(wraps=buffer)

                def write_or_fail(line: str) -> int:
                    """Fail at model step start, completion, or final run event."""
                    if stream.write.call_count == failing_write:
                        raise OSError("simulated write failure")
                    return buffer.write(line)

                stream.write.side_effect = write_or_fail
                with patch("run_logging.open", return_value=stream, create=True):
                    code, stdout, stderr = self.call_main([
                        str(SAMPLE_PATH), "--model-report", "--log-dir", str(self.log_dir),
                    ])
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertIn("Protokollierung", stderr)
                self.assertNotIn("Traceback", stderr)
                self.assertTrue(buffer.closed)
                stream.close.assert_called_once()
                self.assertEqual(stream.write.call_count, failing_write)
                self.assertEqual(self.generator.call_count, 0 if failing_write == 6 else 1)

    def test_custom_processing_exception_is_preserved(self) -> None:
        """Logging understands arbitrary processing errors without importing a provider."""
        class ProcessingError(Exception):
            """Stand in for an independent component's custom exception."""

        original = ProcessingError("private-error-marker")
        with self.assertRaises(ProcessingError) as caught:
            with log_run(self.log_dir) as logger:
                with log_step(logger, "model_report"):
                    raise original

        self.assertIs(caught.exception, original)
        events = self.read_events(next(self.log_dir.glob("*.jsonl")))
        self.assertEqual(len(events), 4)
        for event in events[-2:]:
            self.assertEqual(event["status"], "error")
            self.assertEqual(event["error_type"], "ProcessingError")
        self.assertNotIn("private-error-marker", json.dumps(events))

    def test_duration_uses_counter_despite_wall_clock_moving_backwards(self) -> None:
        """Controlled clocks demonstrate that UTC timestamps do not set durations."""
        wall_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with patch("run_logging.time.perf_counter", side_effect=[10, 11, 12.5, 14]):
            with patch("run_logging.datetime") as clock:
                clock.now.side_effect = [wall_time - timedelta(seconds=n) for n in range(4)]
                with log_run(self.log_dir) as logger:
                    with log_step(logger, "csv_import"):
                        pass

        events = self.read_events(next(self.log_dir.glob("*.jsonl")))
        self.assertAlmostEqual(events[2]["duration_ms"], 1500.0)
        self.assertAlmostEqual(events[3]["duration_ms"], 4000.0)
        self.assertLess(events[-1]["timestamp"], events[0]["timestamp"])

    def test_help_and_argument_errors_create_no_logs(self) -> None:
        """Argument parsing must finish before the log directory is created."""
        cases = [
            (["--help"], 0),
            ([], 2),
            ([str(SAMPLE_PATH), "--threshold", "NaN"], 2),
            ([str(SAMPLE_PATH), "--unknown"], 2),
        ]
        for arguments, expected_code in cases:
            with self.subTest(arguments=arguments):
                completed = self.run_cli(["--log-dir", str(self.log_dir), *arguments])
                self.assertEqual(completed.returncode, expected_code)
                self.assertFalse(self.log_dir.exists())

    def test_without_option_output_is_unchanged_and_no_log_is_created(self) -> None:
        """Optional logging neither changes the report nor creates implicit files."""
        without_log = self.run_cli([str(SAMPLE_PATH)])
        self.assertEqual(list(self.root.iterdir()), [])
        with_log = self.run_cli([str(SAMPLE_PATH), "--log-dir", str(self.log_dir)])

        self.assertEqual(without_log.returncode, 0)
        self.assertEqual(with_log.returncode, 0)
        self.assertEqual(without_log.stdout, with_log.stdout)
        self.assertEqual(without_log.stderr, "")
        self.assertEqual(with_log.stderr, "")
