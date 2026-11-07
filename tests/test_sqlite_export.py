"""Check archived approval and exclusive export with real SQLite and UTF-8 files."""

import hashlib
import io
import os
import tempfile
import unittest
from contextlib import chdir, closing, redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import cosi
from openai_text import OpenAITextResult
from report_storage import write_report
from sqlite_storage import SQLiteStorageError, finish_export, open_database, record_export_decision


PROJECT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_PATH = PROJECT_DIR / "examples/temperature_sample.csv"
QUERY = (PROJECT_DIR / "db/exports_query.sql").read_text(encoding="utf-8")


class SQLiteExportTests(unittest.TestCase):
    """Observe committed state at input/write boundaries; never contact a model."""

    def setUp(self) -> None:
        """Keep files temporary and supply a fixed typed result at the API boundary."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.database = self.root / "runs.sqlite3"
        self.target = self.root / "reports/result.txt"
        self.output = io.StringIO()
        self.errors = io.StringIO()
        self.fixed_result = OpenAITextResult(
            text="Simulierter Bericht: Grüße.\r\n  ", requested_model="gpt-4.1-mini",
            returned_model=None, response_id=None, request_id=None,
            input_tokens=None, output_tokens=None, total_tokens=None, duration_ms=1.0,
        )
        boundaries = (
            patch.dict(os.environ, {}, clear=True),
            patch("socket.create_connection", side_effect=AssertionError("No network.")),
            patch("openai_text.http.client.HTTPSConnection", side_effect=AssertionError("No API.")),
            patch("cosi.generate_text", side_effect=AssertionError("Use typed adapter with database.")),
            patch("cosi.new_report_path", return_value=self.target),
        )
        for boundary in boundaries:
            boundary.start()
            self.addCleanup(boundary.stop)
        model = patch("cosi.generate_text_result", return_value=self.fixed_result)
        self.model = model.start()
        self.addCleanup(model.stop)

    def run_cli(self, answer="ja", *, model: bool = False) -> int:
        """Run the real CLI while replacing only terminal input and external model."""
        self.output.seek(0)
        self.output.truncate()
        self.errors.seek(0)
        self.errors.truncate()
        if callable(answer) or isinstance(answer, BaseException):
            input_patch = patch("cosi.input", side_effect=answer, create=True)
        else:
            input_patch = patch("cosi.input", return_value=answer, create=True)
        options = [str(SAMPLE_PATH), "--database", str(self.database), "--save-report"]
        if model:
            options.append("--model-report")
        with chdir(self.root), redirect_stdout(self.output), redirect_stderr(self.errors), input_patch:
            return cosi.main(options)

    def preview(self) -> str:
        """Extract exactly the displayed report, excluding preview marker lines."""
        return self.output.getvalue().split("--- Bericht beginnt ---\n", 1)[1].split("--- Bericht endet ---\n", 1)[0]

    def query(self) -> list[dict]:
        """Read the public join query on a new connection after the CLI returns."""
        with closing(open_database(self.database)) as connection:
            cursor = connection.execute(QUERY)
            names = [item[0] for item in cursor.description]
            return [dict(zip(names, row)) for row in cursor]

    def inspect_at_input(self, expected_model: bool) -> str:
        """Prove exact archive/preview identity and no write lock during input."""
        with closing(open_database(self.database)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                report = connection.execute(
                    "SELECT content_text, content_sha256, byte_count FROM artifacts WHERE kind = 'report'"
                ).fetchone()
                self.assertEqual(report[0], self.preview())
                content = report[0].encode("utf-8")
                self.assertEqual(report[1:], (hashlib.sha256(content).hexdigest(), len(content)))
                self.assertEqual(connection.execute("SELECT status, finished_at FROM runs").fetchall(), [("running", None)])
                self.assertEqual(connection.execute("SELECT count(*) FROM approvals").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT count(*) FROM exports").fetchone()[0], 0)
                calls = connection.execute("SELECT status FROM model_calls").fetchall()
                self.assertEqual(calls, [("succeeded",)] if expected_model else [])
        self.assertIn(f"Zielpfad: {self.target}", self.output.getvalue())
        self.assertFalse(self.target.exists())
        return " \tJa \n"

    def test_approval_with_and_without_model_commits_start_before_exact_export(self) -> None:
        """Preview, archive and UTF-8 file agree; approval/export start precede I/O."""
        for model in (False, True):
            with self.subTest(model=model):
                self.database = self.root / f"approved-{model}.sqlite3"
                self.target = self.root / f"approved-{model}/report.txt"
                with patch("cosi.new_report_path", return_value=self.target):
                    def approve(prompt: str) -> str:
                        return self.inspect_at_input(model)

                    def inspect_write(path: Path, report: str) -> None:
                        with closing(open_database(self.database)) as connection:
                            with connection:
                                connection.execute("BEGIN IMMEDIATE")
                                row = connection.execute(QUERY).fetchone()
                                self.assertEqual((row[1], row[5], row[6], row[7], row[8]),
                                                 ("running", "approved", "explicit_yes", str(path), "started"))
                        self.assertFalse(path.exists())
                        self.assertEqual(report, self.preview())
                        write_report(path, report)

                    with patch("cosi.write_report", side_effect=inspect_write) as writer:
                        self.assertEqual(self.run_cli(approve, model=model), 0)
                    writer.assert_called_once()
                row = self.query()[0]
                self.assertEqual((row["run_status"], row["export_status"], row["file_state"]),
                                 ("succeeded", "succeeded", "complete"))
                content = self.target.read_bytes()
                self.assertEqual(content, self.preview().encode("utf-8"))
                self.assertEqual((row["byte_count"], row["written_bytes"]), (len(content), len(content)))
                self.assertEqual(row["content_sha256"], hashlib.sha256(content).hexdigest())
                self.assertEqual(self.errors.getvalue(), "")
                self.assertIn("Bericht gespeichert:", self.output.getvalue())
        self.model.assert_called_once()

    def test_declines_eof_and_interrupt_keep_archive_without_export_or_file(self) -> None:
        """Only normalized ja approves; declined runs finish successfully in SQLite."""
        cases = (("nein", "not_approved"), ("ja bitte", "not_approved"),
                 ("", "not_approved"), (EOFError(), "eof"), (KeyboardInterrupt(), "interrupted"))
        for model in (False, True):
            for index, (answer, reason) in enumerate(cases):
                with self.subTest(model=model, answer=answer):
                    self.database = self.root / f"declined-{model}-{index}.sqlite3"
                    with patch("cosi.write_report") as writer:
                        self.assertEqual(self.run_cli(answer, model=model), 0)
                    writer.assert_not_called()
                    row = self.query()[0]
                    self.assertEqual((row["run_status"], row["decision"], row["reason_code"], row["export_status"]),
                                     ("succeeded", "declined", reason, None))
                    self.assertEqual(row["target_path"], str(self.target))
                    self.assertFalse(self.target.parent.exists())
                    self.assertIn("Nicht gespeichert: keine Freigabe.", self.output.getvalue())

    def test_existing_target_is_untouched_and_export_and_run_fail(self) -> None:
        """A collision preserves the original file, archive and explicit approval."""
        self.target.parent.mkdir()
        original = b"existing file\x00"
        self.target.write_bytes(original)
        for model in (False, True):
            with self.subTest(model=model):
                self.database = self.root / f"collision-{model}.sqlite3"
                with patch("cosi.write_report", wraps=write_report) as writer:
                    self.assertEqual(self.run_cli("ja", model=model), 1)
                writer.assert_called_once()
                self.assertEqual(self.target.read_bytes(), original)
                row = self.query()[0]
                self.assertEqual((row["run_status"], row["decision"], row["export_status"], row["error_code"]),
                                 ("failed", "approved", "failed", "file_exists"))
                self.assertEqual((row["file_state"], row["written_bytes"]), ("unknown", None))
                self.assertIn("Fehler beim Speichern des Berichts", self.errors.getvalue())
                self.assertNotIn("Bericht gespeichert:", self.output.getvalue())
                with closing(open_database(self.database)) as connection:
                    self.assertEqual(connection.execute("SELECT error_code FROM runs").fetchone()[0], "file_exists")

    def test_file_write_error_retains_approval_and_marks_both_lifecycles_failed(self) -> None:
        """A failed write records safe diagnostics without claiming a complete file."""
        with patch("cosi.write_report", side_effect=OSError("simulated disk error")) as writer:
            self.assertEqual(self.run_cli("ja"), 1)
        writer.assert_called_once()
        row = self.query()[0]
        self.assertEqual((row["decision"], row["run_status"], row["export_status"], row["error_code"]),
                         ("approved", "failed", "failed", "file_error"))
        self.assertFalse(self.target.exists())

    def test_database_failure_after_file_write_reports_missing_confirmation_without_retry(self) -> None:
        """Fail the last UPDATE: the file exists, but export/run confirmation rolls back."""
        def invalid_run_duration(path, export, **options):
            options["run_duration_ms"] = -1.0
            return finish_export(path, export, **options)

        for model in (False, True):
            with self.subTest(model=model):
                self.database = self.root / f"unconfirmed-{model}.sqlite3"
                self.target = self.root / f"unconfirmed-{model}/report.txt"
                with patch("cosi.new_report_path", return_value=self.target):
                    with patch("cosi.finish_export", side_effect=invalid_run_duration):
                        with patch("cosi.write_report", wraps=write_report) as writer:
                            self.assertEqual(self.run_cli("ja", model=model), 1)
                writer.assert_called_once()
                self.assertEqual(self.target.read_bytes(), self.preview().encode("utf-8"))
                row = self.query()[0]
                self.assertEqual((row["run_status"], row["decision"], row["export_status"]),
                                 ("running", "approved", "started"))
                self.assertIn("bereits vollständig geschrieben und geschlossen", self.errors.getvalue())
                self.assertIn("Nur die Bestätigung in der Datenbank fehlt", self.errors.getvalue())
                self.assertNotIn("Bericht gespeichert:", self.output.getvalue())

    def test_archive_or_decision_storage_failure_prevents_file_export(self) -> None:
        """No user approval is sought before archive commit; no I/O before export start."""
        with patch("cosi.archive_analysis_report", side_effect=SQLiteStorageError("archive failure")):
            with patch("cosi.write_report") as writer:
                self.assertEqual(self.run_cli(AssertionError("No input before archive.")), 1)
        writer.assert_not_called()
        with patch("cosi.record_export_decision", side_effect=SQLiteStorageError("decision failure")):
            with patch("cosi.write_report") as writer:
                self.assertEqual(self.run_cli("ja"), 1)
        writer.assert_not_called()
        self.assertFalse(self.target.exists())
        row = self.query()[0]
        self.assertEqual((row["run_status"], row["decision"], row["export_status"]), ("running", None, None))

    def test_approval_for_a_different_hash_is_rejected_without_export(self) -> None:
        """Approval must match the archived bytes, not just the report identifier."""
        def wrong_hash(path, report, *args, **options):
            return record_export_decision(path, replace(report, content_sha256="0" * 64), *args, **options)

        with patch("cosi.record_export_decision", side_effect=wrong_hash):
            with patch("cosi.write_report") as writer:
                self.assertEqual(self.run_cli("ja"), 1)
        writer.assert_not_called()
        self.assertFalse(self.target.exists())
        row = self.query()[0]
        self.assertEqual((row["decision"], row["export_status"], row["run_status"]), (None, None, "running"))


if __name__ == "__main__":
    unittest.main()
