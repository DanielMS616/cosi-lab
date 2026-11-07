"""Check read-only run overviews with real SQLite fixtures and no model access."""

import io
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import cosi_runs
from openai_text import OpenAITextError, OpenAITextResult
from run_record import AnalysisRun, ApprovalDecision
from sqlite_storage import (
    SCHEMA_PATH, complete_model_run, fail_model_run, finish_export, open_database,
    open_readonly_database, prepare_model_run, record_export_decision, save_analysis_run,
)


SAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples/temperature_sample.csv"


def timestamp(hour: int, minute: int = 0) -> str:
    """Use fixed-width UTC fixture timestamps so newest ordering is observable."""
    return f"2026-11-07T{hour:02}:{minute:02}:00.000000Z"


class CosiRunsTests(unittest.TestCase):
    """Verify metadata selection/output; fixture outcomes do not test a real model."""

    def setUp(self) -> None:
        """Keep all databases outside the repository and prohibit HTTP access."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.database = self.root / "runs.sqlite3"
        boundary = patch("openai_text.http.client.HTTPSConnection", side_effect=AssertionError("No API in overview tests."))
        boundary.start()
        self.addCleanup(boundary.stop)

    def run_record(self, run_id: str, hour: int) -> AnalysisRun:
        """Supply a small successful analysis record for storage fixture creation."""
        return AnalysisRun(
            run_id=run_id, input_path=SAMPLE_PATH, input_bytes=SAMPLE_PATH.read_bytes(),
            analysis={"total_count": 6, "valid_count": 5, "missing_count": 1,
                      "minimum": 40.0, "maximum": 65.0, "mean": 53.6, "exceedance_count": 2},
            threshold=60.0, started_at=timestamp(hour), finished_at=timestamp(hour, 1), duration_ms=1.0,
        )

    def model_report(self, run_id: str, hour: int, *, fail: bool = False):
        """Prepare a real stored call, then finalize it with fixed result/diagnosis."""
        call = prepare_model_run(
            self.database, self.run_record(run_id, hour), prompt="PRIVATE_PROMPT_MARKER",
            model="requested-model", started_at=timestamp(hour, 1),
        )
        if fail:
            fail_model_run(
                self.database, call, error=OpenAITextError("private error", error_code="http_error", http_status=429),
                finished_at=timestamp(hour, 2), run_duration_ms=2.0, call_duration_ms=1.0,
            )
            return None
        result = OpenAITextResult(
            text="PRIVATE_RESPONSE_MARKER", requested_model="requested-model", returned_model="returned-snapshot",
            response_id=None, request_id=None, input_tokens=None, output_tokens=None, total_tokens=None, duration_ms=1.0,
        )
        return complete_model_run(
            self.database, call, result=result, report="PRIVATE_REPORT_MARKER",
            finished_at=timestamp(hour, 2), run_duration_ms=2.0, keep_run_open=True,
        )

    def export_run(self, run_id: str, hour: int, *, finish: bool = True):
        """Seed approved export metadata; no file-writing behavior is under test here."""
        report = self.model_report(run_id, hour)
        export = record_export_decision(
            self.database, report, self.root / f"{run_id}.txt", ApprovalDecision(True, "explicit_yes"),
            decided_at=timestamp(hour, 3), run_duration_ms=3.0,
        )
        if finish:
            finish_export(self.database, export, finished_at=timestamp(hour, 4), duration_ms=1.0, run_duration_ms=4.0)
        return report

    def call_main(self, extra: list[str] | None = None) -> tuple[int, str, str]:
        """Capture only the public overview command's output and exit code."""
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
            try:
                code = cosi_runs.main(["--database", str(self.database), *(extra or [])])
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def test_analysis_model_error_and_export_are_displayed_newest_first(self) -> None:
        """Three run types produce exactly three lines with metadata and no content."""
        save_analysis_run(self.database, self.run_record("analysis-run", 10))
        self.model_report("error-run", 11, fail=True)
        self.export_run("export-run", 12)
        original = self.database.read_bytes()
        code, output, errors = self.call_main(["--limit", "20"])
        self.assertEqual((code, errors), (0, ""))
        lines = output.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("export-run | " + timestamp(12)))
        self.assertIn("temperature_report | status=succeeded", lines[0])
        self.assertIn("model_returned=returned-snapshot", lines[0])
        self.assertIn("approval=approved | export=succeeded", lines[0])
        self.assertTrue(lines[1].startswith("error-run | " + timestamp(11)))
        self.assertIn("status=failed", lines[1])
        self.assertIn("run_error_code=http_error", lines[1])
        self.assertIn("model_error_code=http_error | http_status=429", lines[1])
        self.assertNotIn("model_returned=", lines[1])
        self.assertEqual(lines[2], "analysis-run | " + timestamp(10) + " | temperature_analysis | status=succeeded")
        for marker in ("PRIVATE_PROMPT_MARKER", "PRIVATE_RESPONSE_MARKER", "PRIVATE_REPORT_MARKER", "private error"):
            self.assertNotIn(marker, output)
        self.assertEqual(self.database.read_bytes(), original)
        code, output, errors = self.call_main(["--limit", "1"])
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(output.splitlines(), [lines[0]])

    def test_multiple_calls_and_decisions_do_not_duplicate_or_mix_exports(self) -> None:
        """Newest timestamps win; an older approval's export cannot leak into a decline."""
        report = self.export_run("multiple-run", 12)
        with closing(open_database(self.database)) as connection:
            with connection:
                # Append schema-valid evidence for a run with multiple calls. A
                # higher index alone must not override a later start timestamp.
                for call_id, index, minute, model in (("latest-call", 2, 6, "latest-model"),
                                                       ("middle-call", 3, 5, "middle-model")):
                    connection.execute(
                        """INSERT INTO model_calls (
                            call_id, run_id, call_index, input_artifact_id, provider, model_requested,
                            model_returned, prompt_text, prompt_sha256, request_json, started_at,
                            finished_at, duration_ms, status, response_text
                        ) SELECT ?, run_id, ?, input_artifact_id, provider, model_requested,
                                 ?, prompt_text, prompt_sha256, request_json, ?, ?, 1.0, 'succeeded', response_text
                          FROM model_calls WHERE run_id = ? AND call_index = 1""",
                        (call_id, index, model, timestamp(12, minute), timestamp(12, minute + 1), "multiple-run"),
                    )
                connection.execute(
                    """INSERT INTO approvals (approval_id, run_id, artifact_id, action, target_path,
                        content_sha256, decision, reason_code, actor, decided_at)
                       VALUES ('latest-decline', ?, ?, 'export_report', 'declined-target.txt', ?,
                               'declined', 'not_approved', 'test', ?)""",
                    (report.run_id, report.artifact_id, report.content_sha256, timestamp(12, 8)),
                )
        code, output, errors = self.call_main()
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(len(output.splitlines()), 1)
        self.assertIn("model_returned=latest-model", output)
        self.assertNotIn("middle-model", output)
        self.assertIn("approval=declined", output)
        self.assertNotIn("export=", output)
        with closing(open_database(self.database)) as connection:
            with connection:
                connection.execute(
                    """INSERT INTO approvals (approval_id, run_id, artifact_id, action, target_path,
                        content_sha256, decision, reason_code, actor, decided_at)
                       VALUES ('new-approved', ?, ?, 'export_report', 'new-target.txt', ?,
                               'approved', 'explicit_yes', 'test', ?)""",
                    (report.run_id, report.artifact_id, report.content_sha256, timestamp(12, 9)),
                )
                connection.execute(
                    """INSERT INTO exports (export_id, run_id, artifact_id, approval_id,
                        target_path, content_sha256, started_at, finished_at, duration_ms,
                        status, file_state, error_code)
                       VALUES ('new-export', ?, ?, 'new-approved', 'new-target.txt', ?, ?, ?,
                               1.0, 'failed', 'unknown', 'file_error')""",
                    (report.run_id, report.artifact_id, report.content_sha256, timestamp(12, 9), timestamp(12, 10)),
                )
        code, output, errors = self.call_main()
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(len(output.splitlines()), 1)
        self.assertIn("approval=approved | export=failed | export_error_code=file_error", output)
        self.assertNotIn("export=succeeded", output)

    def test_running_and_started_are_explicitly_unconfirmed(self) -> None:
        """Open model calls and open exports must not appear as confirmed completions."""
        prepare_model_run(self.database, self.run_record("pending-model", 10),
                          prompt="PRIVATE_PROMPT_MARKER", model="requested", started_at=timestamp(10, 1))
        self.export_run("pending-export", 11, finish=False)
        code, output, errors = self.call_main()
        self.assertEqual((code, errors), (0, ""))
        lines = output.splitlines()
        self.assertIn("status=running", lines[0])
        self.assertIn("export=started", lines[0])
        self.assertIn("kein Abschluss gespeichert: Lauf, Export", lines[0])
        self.assertIn("model_status=started", lines[1])
        self.assertIn("kein Abschluss gespeichert: Lauf, Modellaufruf", lines[1])

    def test_readonly_mode_enforces_no_writes_and_handles_uri_characters(self) -> None:
        """mode=ro must be enforced by SQLite, including escaped Unicode/?/# paths."""
        self.database = self.root / "Übersicht ? #.sqlite3"
        save_analysis_run(self.database, self.run_record("readonly-run", 10))
        original = self.database.read_bytes()
        original_connect = sqlite3.connect
        with patch("sqlite_storage.sqlite3.connect", wraps=original_connect) as connect:
            with closing(open_readonly_database(self.database)) as connection:
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(connection.execute("PRAGMA recursive_triggers").fetchone()[0], 1)
                with self.assertRaisesRegex(sqlite3.OperationalError, "readonly"):
                    connection.execute("CREATE TABLE forbidden (value TEXT)")
        file_calls = [call for call in connect.call_args_list if str(call.args[0]).startswith("file:")]
        self.assertEqual(len(file_calls), 1)
        self.assertTrue(file_calls[0].args[0].endswith("?mode=ro"))
        self.assertTrue(file_calls[0].kwargs["uri"])
        self.assertEqual(self.database.read_bytes(), original)

    def test_missing_database_path_creates_neither_file_nor_directory(self) -> None:
        """A nonexistent --database target must fail read-only without side effects."""
        self.database = self.root / "missing/never.sqlite3"
        code, output, errors = self.call_main()
        self.assertEqual((code, output), (1, ""))
        self.assertIn("Datenbankdatei nicht gefunden", errors)
        self.assertFalse(self.database.parent.exists())

    def test_incompatible_files_are_rejected_without_modification(self) -> None:
        """Foreign, future, altered, empty and non-SQLite files produce clear errors."""
        for case in ("foreign", "future", "altered", "empty", "not-sqlite"):
            with self.subTest(case=case):
                self.database.unlink(missing_ok=True)
                if case in ("empty", "not-sqlite"):
                    self.database.write_bytes(b"" if case == "empty" else b"not a database")
                else:
                    with closing(sqlite3.connect(self.database)) as connection:
                        if case == "foreign":
                            connection.execute("CREATE TABLE foreign_data (value TEXT)")
                        else:
                            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
                            if case == "future":
                                connection.execute("PRAGMA user_version = 99")
                            else:
                                connection.execute("DROP TRIGGER artifacts_deny_delete")
                original = self.database.read_bytes()
                code, output, errors = self.call_main()
                self.assertEqual((code, output), (1, ""))
                self.assertIn("Fehler beim Lesen der Laufübersicht", errors)
                self.assertNotIn("Traceback", errors)
                self.assertEqual(self.database.read_bytes(), original)

    def test_invalid_arguments_fail_before_opening_database(self) -> None:
        """Missing paths and invalid limits are CLI argument errors, not DB writes."""
        with patch("sqlite_storage.sqlite3.connect") as connect:
            for limit in ("0", "-1", "abc", "1.5", str(2**63)):
                code, output, errors = self.call_main(["--limit", limit])
                self.assertEqual((code, output), (2, ""))
                self.assertIn("positive Ganzzahl", errors)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                cosi_runs.main([])
            self.assertEqual(caught.exception.code, 2)
            connect.assert_not_called()
        self.assertFalse(self.database.exists())

    def test_empty_database_and_control_characters_keep_one_line_per_run(self) -> None:
        """An empty valid DB has no rows; metadata control characters are escaped."""
        with closing(sqlite3.connect(self.database)) as connection:
            connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(self.call_main(), (0, "", ""))
        save_analysis_run(self.database, self.run_record("run\nwith\tescape\x1b", 10))
        code, output, errors = self.call_main()
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(len(output.splitlines()), 1)
        self.assertIn(r"run\nwith\tescape\u001b", output)
        self.assertNotIn("\x1b", output)


if __name__ == "__main__":
    unittest.main()
