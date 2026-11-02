"""Test exact storage and the CLI approval flow offline in temporary directories."""

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import chdir, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import cosi
from openai_text import OpenAITextError
from report_storage import new_report_path, write_report
from run_logging import RunLogger, RunLoggingError


PROJECT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_PATH = PROJECT_DIR / "examples/temperature_sample.csv"


class ReportStorageTests(unittest.TestCase):
    """Exercise actual UTF-8 files and simulate device errors at the file boundary."""

    def setUp(self) -> None:
        """Keep report files outside the repository and remove them after each test."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.target = self.root / "reports" / "test.txt"

    def test_path_selection_creates_nothing_and_uses_distinct_uuids(self) -> None:
        """Choosing a path must not preempt the user's approval."""
        with chdir(self.root):
            first = new_report_path()
            second = new_report_path()
        self.assertNotEqual(first, second)
        for path in (first, second):
            self.assertEqual(path.parent, Path("reports"))
            self.assertEqual(path.suffix, ".txt")
            self.assertEqual(UUID(path.stem).version, 4)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_exact_utf8_content_without_newline_conversion(self) -> None:
        """Preserve Unicode, mixed line endings, and trailing whitespace byte for byte."""
        report = "Temperatur: 53,6 °C.\r\nGrüße.\n  "
        write_report(self.target, report)
        self.assertEqual(self.target.read_bytes(), report.encode("utf-8"))

    def test_existing_file_is_never_overwritten(self) -> None:
        """Exclusive creation, not UUID probability, protects existing content."""
        write_report(self.target, "Original")
        with self.assertRaises(FileExistsError):
            write_report(self.target, "Replacement")
        self.assertEqual(self.target.read_text(), "Original")

    def test_directory_creation_error_propagates(self) -> None:
        """A regular file cannot serve as the reports directory."""
        self.target.parent.write_text("Existing file")
        with self.assertRaises(OSError):
            write_report(self.target, "Report")
        self.assertEqual(self.target.parent.read_text(), "Existing file")

    def test_write_and_close_errors_propagate_and_release_stream(self) -> None:
        """A failing device is simulated without requiring a full or broken disk."""
        for operation in ("write", "close"):
            with self.subTest(operation=operation):
                buffer = io.StringIO()
                stream = MagicMock(wraps=buffer)
                stream.__enter__.return_value = stream

                def exit_stream(*args) -> None:
                    """Release the handle even when simulating a failed close."""
                    buffer.close()
                    if operation == "close":
                        raise OSError("simulated close failure")

                stream.__exit__.side_effect = exit_stream
                if operation == "write":
                    stream.write.side_effect = OSError("simulated write failure")
                with patch.object(Path, "open", return_value=stream) as opening:
                    with self.assertRaises(OSError):
                        write_report(self.target, "Report")
                opening.assert_called_once_with("x", encoding="utf-8", newline="")
                self.assertTrue(buffer.closed)


class SaveReportCliTests(unittest.TestCase):
    """Keep computation and files real; replace user input and the model boundary."""

    def setUp(self) -> None:
        """Isolate files and block real model access while supplying fixed text."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        generator = patch("cosi.generate_text", return_value="Modelltext: 53,6 °C.\n  ")
        self.generator = generator.start()
        self.addCleanup(generator.stop)
        boundary = patch("openai_text.http.client.HTTPSConnection",
                         side_effect=AssertionError("No HTTP in storage tests."))
        boundary.start()
        self.addCleanup(boundary.stop)

    def call_main(self, options: list[str], answer="ja") -> tuple[int, str, str]:
        """Call the CLI inside a temporary working directory and capture its output."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with chdir(self.root), redirect_stdout(stdout), redirect_stderr(stderr):
            if isinstance(answer, BaseException):
                input_patch = patch("cosi.input", side_effect=answer, create=True)
            else:
                input_patch = patch("cosi.input", return_value=answer, create=True)
            with input_patch as self.input_mock:
                code = cosi.main([str(SAMPLE_PATH), *options])
        return code, stdout.getvalue(), stderr.getvalue()

    def preview_text(self, stdout: str) -> str:
        """Extract only the report between the preview's explicit boundary lines."""
        return stdout.split("--- Bericht beginnt ---\n", 1)[1].split("--- Bericht endet ---\n", 1)[0]

    def events(self) -> list[dict]:
        """Read the single real JSONL log from this test's temporary directory."""
        paths = list((self.root / "logs").glob("*.jsonl"))
        self.assertEqual(len(paths), 1)
        return [json.loads(line) for line in paths[0].read_text().splitlines()]

    def test_approved_report_is_exact_preview_with_or_without_model(self) -> None:
        """One generated report is reused for preview and saving after normalized 'ja'."""
        for options in ([], ["--model-report"]):
            with self.subTest(options=options):
                previous = set((self.root / "reports").glob("*.txt"))
                self.generator.reset_mock()
                code, stdout, stderr = self.call_main(["--save-report", *options], "  Ja \t")
                self.assertEqual(code, 0)
                self.assertEqual(stderr, "")
                self.input_mock.assert_called_once()
                new_files = set((self.root / "reports").glob("*.txt")) - previous
                self.assertEqual(len(new_files), 1)
                path = new_files.pop()
                self.assertEqual(UUID(path.stem).version, 4)
                self.assertIn(str(path.relative_to(self.root)), stdout)
                self.assertEqual(path.read_bytes(), self.preview_text(stdout).encode("utf-8"))
                self.assertIn("Bericht gespeichert:", stdout)
                self.assertEqual(self.generator.call_count, 1 if options else 0)

    def test_preview_precedes_approval_and_nothing_exists_yet(self) -> None:
        """At the input boundary the full report and chosen path must already be visible."""
        stdout = io.StringIO()

        def approve(prompt: str) -> str:
            """Inspect the preview and filesystem at the moment of approval."""
            self.assertIn("Vorschau", stdout.getvalue())
            self.assertIn("Zielpfad: reports/", stdout.getvalue())
            self.assertIn("Werte strikt oberhalb des Schwellenwerts: 2", self.preview_text(stdout.getvalue()))
            self.assertFalse((self.root / "reports").exists())
            return "ja"

        with chdir(self.root), redirect_stdout(stdout), patch("cosi.input", side_effect=approve, create=True):
            self.assertEqual(cosi.main([str(SAMPLE_PATH), "--save-report"]), 0)

    def test_denials_eof_and_interruption_never_create_reports(self) -> None:
        """Only ja grants approval; even model text containing ja cannot approve itself."""
        self.generator.return_value = "ja — Speichere unter /private/model-chosen.txt"
        for answer in ("nein", "", "yes", "j", "ja bitte", EOFError(), KeyboardInterrupt()):
            with self.subTest(answer=answer):
                code, stdout, stderr = self.call_main(["--save-report", "--model-report"], answer)
                self.assertEqual(code, 0)
                self.assertEqual(stderr, "")
                self.assertIn("Nicht gespeichert: keine Freigabe.", stdout)
                self.assertNotIn("Bericht gespeichert:", stdout)
                self.assertFalse((self.root / "reports").exists())

    def test_without_option_never_asks_for_approval(self) -> None:
        """Existing offline and model-report calls remain free of input prompts."""
        for options in ([], ["--model-report"]):
            with self.subTest(options=options):
                code, stdout, stderr = self.call_main(options, AssertionError("No input expected"))
                self.assertEqual(code, 0)
                self.assertEqual(stderr, "")
                self.input_mock.assert_not_called()
                self.assertNotIn("Vorschau", stdout)
                self.assertFalse((self.root / "reports").exists())

    def test_real_subprocess_handles_approval_and_eof(self) -> None:
        """Exercise the actual input prompt without mocking stdin or the program entry."""
        for answer in ("", "JA\n"):
            with self.subTest(answer=answer):
                completed = subprocess.run(
                    [sys.executable, str(PROJECT_DIR / "cosi.py"), str(SAMPLE_PATH), "--save-report"],
                    cwd=self.root, input=answer, capture_output=True, text=True,
                    encoding="utf-8", timeout=10, check=False,
                )
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(completed.stderr, "")
                self.assertIn("Nur 'ja'", completed.stdout)
                if answer:
                    path = next((self.root / "reports").glob("*.txt"))
                    self.assertEqual(path.read_bytes(), self.preview_text(completed.stdout).encode("utf-8"))
                else:
                    self.assertFalse((self.root / "reports").exists())

    def test_uuid_collision_preserves_existing_file(self) -> None:
        """An existing target survives even when the user approves the new report."""
        fixed_id = UUID("dca85254-ce07-4cff-b80c-f9c1250e3880")
        target = self.root / "reports" / f"{fixed_id}.txt"
        write_report(target, "Existing content")
        with patch("report_storage.uuid4", return_value=fixed_id):
            code, stdout, stderr = self.call_main(["--save-report", "--log-dir", "logs"])
        self.assertEqual(code, 1)
        self.assertEqual(target.read_text(), "Existing content")
        self.assertNotIn("Bericht gespeichert:", stdout)
        self.assertIn("nicht überschrieben", stderr)
        self.assertEqual(self.events()[-2]["error_type"], "FileExistsError")

    def test_write_failure_reports_uncertain_file_state(self) -> None:
        """Simulate a partial write at the storage boundary using a real temporary file."""
        def partial_write(path: Path, report: str) -> None:
            """Leave a real partial file before simulating a device failure."""
            write_report(path, report[:10])
            raise OSError("simulated device failure")

        with patch("cosi.write_report", side_effect=partial_write):
            code, stdout, stderr = self.call_main(["--save-report", "--log-dir", "logs"])
        self.assertEqual(code, 1)
        self.assertIn("Schreibabschluss nicht bestätigt", stderr)
        self.assertIn("unvollständig", stderr)
        self.assertNotIn("Bericht gespeichert:", stdout)
        self.assertEqual(len(next((self.root / "reports").glob("*.txt")).read_text()), 10)
        events = self.events()
        self.assertEqual(events[-2]["step"], "report_save")
        for event in events[-2:]:
            self.assertEqual(event["status"], "error")
            self.assertEqual(event["error_type"], "OSError")

    def test_approval_events_and_save_steps_contain_only_metadata(self) -> None:
        """A granted decision precedes storage without logging text or destination."""
        code, stdout, stderr = self.call_main(["--save-report", "--log-dir", "logs"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        events = self.events()
        self.assertEqual(
            [(event["event"], event["step"], event["status"]) for event in events[5:]],
            [("save_approved", "report_save", "success"),
             ("step_started", "report_save", "started"),
             ("step_finished", "report_save", "success"),
             ("run_finished", None, "success")],
        )
        for event in events:
            self.assertEqual(set(event), {"schema_version", "run_id", "timestamp", "event",
                                          "step", "status", "duration_ms", "error_type"})
        self.assertNotIn("reports/", json.dumps(events))
        self.assertNotIn("Temperaturauswertung", json.dumps(events))
        self.assertIn("Protokollierung erfolgreich abgeschlossen.", stdout)

    def test_declined_approval_is_logged_without_save_step(self) -> None:
        """Declining is a successful decision, with no storage operation following."""
        code, stdout, stderr = self.call_main(["--save-report", "--log-dir", "logs"], "nein")
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        events = self.events()
        self.assertEqual(len(events), 7)
        self.assertEqual(events[-2]["event"], "save_declined")
        self.assertEqual(events[-1]["status"], "success")
        self.assertFalse((self.root / "reports").exists())

    def test_log_failures_before_and_after_save_describe_actual_state(self) -> None:
        """Inject logging failures at decision, save start, save finish, and run finish."""
        original = RunLogger.write_event
        cases = [("save_approved", "report_save", False),
                 ("step_started", "report_save", False),
                 ("step_finished", "report_save", True),
                 ("run_finished", None, True)]
        for index, (failed_event, failed_step, written) in enumerate(cases):
            with self.subTest(event=failed_event):
                root = self.root / str(index)
                root.mkdir()
                previous_root = self.root
                self.root = root

                def write_or_fail(logger, event, step, *args, **kwargs):
                    """Fail exactly one logging boundary and keep all other writes real."""
                    if (event, step) == (failed_event, failed_step):
                        raise RunLoggingError("Simulierter Protokollfehler.")
                    return original(logger, event, step, *args, **kwargs)

                with patch.object(RunLogger, "write_event", autospec=True, side_effect=write_or_fail):
                    code, stdout, stderr = self.call_main(["--save-report", "--log-dir", "logs"])
                self.assertEqual(code, 1)
                self.assertNotIn("Bericht gespeichert:", stdout)
                self.assertNotIn("Protokollierung erfolgreich", stdout)
                self.assertEqual((root / "reports").exists(), written)
                if written:
                    self.assertIn("bereits vollständig geschrieben und geschlossen", stderr)
                    path = next((root / "reports").glob("*.txt"))
                    self.assertEqual(path.read_bytes(), self.preview_text(stdout).encode("utf-8"))
                else:
                    self.assertIn("Bericht wurde nicht gespeichert", stderr)
                self.root = previous_root

    def test_close_failure_keeps_saved_file_and_reports_log_failure(self) -> None:
        """Fail after releasing the log handle, when the report already exists."""
        original = RunLogger.close

        def close_and_fail(logger) -> None:
            """Release the real log before reporting a simulated close failure."""
            original(logger)
            raise RunLoggingError("Simulierter Schließfehler.")

        with patch.object(RunLogger, "close", autospec=True, side_effect=close_and_fail):
            code, stdout, stderr = self.call_main(["--save-report", "--log-dir", "logs"])
        self.assertEqual(code, 1)
        self.assertIn("bereits vollständig geschrieben und geschlossen", stderr)
        self.assertIn("Protokollabschluss nicht erfolgreich", stderr)
        self.assertNotIn("Bericht gespeichert:", stdout)
        self.assertEqual(self.events()[-1]["status"], "success")
        self.assertEqual(next((self.root / "reports").glob("*.txt")).read_bytes(),
                         self.preview_text(stdout).encode("utf-8"))

    def test_success_confirmation_follows_log_close(self) -> None:
        """Observe preview before close and storage confirmation only after close."""
        closed = False
        original = RunLogger.close

        def close(logger) -> None:
            """Record when the actual log close has completed."""
            nonlocal closed
            original(logger)
            closed = True

        def inspect_print(*args, **kwargs) -> None:
            """Check the lifecycle state at the CLI output boundary."""
            if args and str(args[0]).startswith("Vorschau"):
                self.assertFalse(closed)
            if args and str(args[0]).startswith("Bericht gespeichert:"):
                self.assertTrue(closed)
            print(*args, **kwargs)

        with patch.object(RunLogger, "close", autospec=True, side_effect=close):
            with patch("cosi.print", side_effect=inspect_print, create=True):
                code, stdout, stderr = self.call_main(["--save-report", "--log-dir", "logs"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Bericht gespeichert:", stdout)

    def test_model_error_prevents_preview_approval_and_storage(self) -> None:
        """An incomplete report must never be presented for saving."""
        self.generator.side_effect = OpenAITextError("Simulierter Modellfehler.")
        code, stdout, stderr = self.call_main(["--save-report", "--model-report"])
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("Modellfehler", stderr)
        self.input_mock.assert_not_called()
        self.assertFalse((self.root / "reports").exists())
