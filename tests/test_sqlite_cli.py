"""Check optional CLI database storage with real temporary SQLite databases."""

import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import chdir, closing, redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import cosi
import sqlite_demo
from run_logging import RunLogger, RunLoggingError
from run_record import AnalysisRun
from sqlite_storage import SQLiteStorageError, open_database, save_analysis_run


SAMPLE_PATH = Path(__file__).resolve().parent.parent / "examples/temperature_sample.csv"


class SQLiteCliTests(unittest.TestCase):
    """Prove persistence and rejection/rollback without model or network access."""

    def setUp(self) -> None:
        """Keep generated files temporary and make accidental API access fail."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.target = self.root / "data/runs.sqlite3"
        for boundary in (
            patch.dict(os.environ, {}, clear=True),
            patch("socket.create_connection", side_effect=AssertionError("No network.")),
            patch("cosi.generate_text", side_effect=AssertionError("No model in database runs.")),
        ):
            boundary.start()
            self.addCleanup(boundary.stop)

    def call_main(self, options: list[str]) -> tuple[int, str, str]:
        """Execute the real CLI parser and processing with isolated output paths."""
        with chdir(self.root), redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
            try:
                code = cosi.main([str(SAMPLE_PATH), *options])
            except SystemExit as error:
                code = error.code
        return code, output.getvalue(), errors.getvalue()

    def snapshot(self) -> tuple[list[tuple], list[tuple]]:
        """Read immutable run evidence after the writer has closed its connection."""
        with closing(open_database(self.target)) as connection:
            return (
                connection.execute("SELECT * FROM runs ORDER BY run_id").fetchall(),
                connection.execute("SELECT * FROM artifacts ORDER BY artifact_id").fetchall(),
            )

    def test_two_calls_append_complete_runs_and_reopen_for_joint_query(self) -> None:
        """Two thresholds must produce distinct linked runs in the same file."""
        for threshold in (60, 65):
            code, output, errors = self.call_main([
                "--database", str(self.target), "--threshold", str(threshold),
            ])
            self.assertEqual((code, errors), (0, ""))
            self.assertIn("Arithmetischer Mittelwert: 53.6", output)
        with closing(open_database(self.target)) as connection:
            rows = connection.execute(
                """SELECT r.run_id, r.settings_json, i.file_path, i.content_sha256,
                          i.byte_count, a.content_text, r.duration_ms
                   FROM runs r
                   JOIN artifacts i ON i.run_id = r.run_id AND i.kind = 'input_file'
                   JOIN artifacts a ON a.run_id = r.run_id
                       AND a.source_artifact_id = i.artifact_id AND a.kind = 'analysis'
                   ORDER BY json_extract(r.settings_json, '$.threshold')"""
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertNotEqual(rows[0][0], rows[1][0])
            for row, threshold, exceedances in zip(rows, (60, 65), (2, 0)):
                self.assertEqual(json.loads(row[1]), {"simulation": False, "threshold": threshold})
                self.assertEqual(Path(row[2]), SAMPLE_PATH)
                self.assertEqual(row[3], hashlib.sha256(SAMPLE_PATH.read_bytes()).hexdigest())
                self.assertEqual(row[4], len(SAMPLE_PATH.read_bytes()))
                self.assertEqual(json.loads(row[5]), {
                    "total_count": 6, "valid_count": 5, "missing_count": 1,
                    "minimum": 40.0, "maximum": 65.0, "mean": 53.6, "exceedance_count": exceedances,
                })
                self.assertGreaterEqual(row[6], 0)
            for table, count in (("runs", 2), ("artifacts", 4), ("model_calls", 0),
                                 ("approvals", 0), ("exports", 0)):
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], count)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            summary_query = (SAMPLE_PATH.parent.parent / "db/analysis_query.sql").read_text()
            summaries = connection.execute(summary_query).fetchall()
            self.assertEqual(len(summaries), 2)
            self.assertEqual([(row[3], row[4], row[5]) for row in summaries],
                             [(60.0, 53.6, 2), (65.0, 53.6, 0)])

    def test_can_append_to_the_existing_demo_schema(self) -> None:
        """The original demo and the new CLI share one unchanged Cosi schema."""
        sqlite_demo.run_demo(self.target)
        original = self.snapshot()
        self.assertEqual(self.call_main(["--database", str(self.target)])[0], 0)
        runs, artifacts = self.snapshot()
        self.assertEqual((len(runs), len(artifacts)), (2, 5))
        self.assertTrue(all(row in runs for row in original[0]))
        self.assertTrue(all(row in artifacts for row in original[1]))

    def test_foreign_database_is_rejected_without_modification(self) -> None:
        """A foreign database must retain its schema, records and exact file bytes."""
        self.target.parent.mkdir()
        with closing(sqlite3.connect(self.target)) as connection:
            with connection:
                connection.execute("CREATE TABLE private_notes (text TEXT)")
                connection.execute("INSERT INTO private_notes VALUES ('keep unchanged')")
        original = self.target.read_bytes()
        code, output, errors = self.call_main(["--database", str(self.target)])
        self.assertEqual((code, output), (1, ""))
        self.assertIn("Keine Cosi-Datenbank", errors)
        self.assertEqual(self.target.read_bytes(), original)

    def test_unknown_version_or_modified_schema_is_rejected(self) -> None:
        """Header markers alone must not authorize writes into a changed schema."""
        self.assertEqual(self.call_main(["--database", str(self.target)])[0], 0)
        with closing(open_database(self.target)) as connection:
            connection.execute("PRAGMA user_version = 99")
        original = self.target.read_bytes()
        code, output, errors = self.call_main(["--database", str(self.target)])
        self.assertEqual((code, output), (1, ""))
        self.assertIn("Unbekannte Cosi-Schemaversion: 99", errors)
        self.assertEqual(self.target.read_bytes(), original)
        with closing(open_database(self.target)) as connection:
            connection.execute("PRAGMA user_version = 1")
            connection.execute("DROP TRIGGER artifacts_deny_delete")
        original = self.target.read_bytes()
        code, output, errors = self.call_main(["--database", str(self.target)])
        self.assertEqual((code, output), (1, ""))
        self.assertIn("Inkompatibles Cosi-Schema", errors)
        self.assertEqual(self.target.read_bytes(), original)

    def test_non_database_and_existing_empty_file_are_rejected(self) -> None:
        """Only absent paths may be initialized; existing arbitrary files stay intact."""
        self.target.parent.mkdir()
        for content in (b"not a database", b""):
            with self.subTest(content=content):
                self.target.write_bytes(content)
                code, output, errors = self.call_main(["--database", str(self.target)])
                self.assertEqual((code, output), (1, ""))
                self.assertIn("Datenbank", errors)
                self.assertEqual(self.target.read_bytes(), content)

    def test_late_constraint_error_rolls_back_only_the_new_run(self) -> None:
        """An invalid analysis fails after run/input INSERTs; all are rolled back."""
        run = AnalysisRun(
            run_id=str(uuid4()), input_path=SAMPLE_PATH, input_bytes=SAMPLE_PATH.read_bytes(),
            analysis=[], threshold=60.0, started_at="2026-11-07T00:00:00.000000Z",
            finished_at="2026-11-07T00:00:00.001000Z", duration_ms=1.0,
        )
        # The deliberately wrong type tests runtime schema validation: annotations
        # alone do not reject arrays, whereas analysis must be a JSON object.
        with self.assertRaises(SQLiteStorageError):
            save_analysis_run(self.target, run)
        self.assertEqual(self.snapshot(), ([], []))
        self.assertEqual(self.call_main(["--database", str(self.target)])[0], 0)
        original = self.snapshot()
        with self.assertRaises(SQLiteStorageError):
            save_analysis_run(self.target, replace(run, run_id=str(uuid4())))
        self.assertEqual(self.snapshot(), original)

    def test_incompatible_options_fail_before_processing_or_creating_files(self) -> None:
        """Forbidden combinations are argument errors even with valid input paths."""
        with patch("cosi.read_temperature_csv") as importer, patch("cosi.save_analysis_run") as save:
            for options in (["--model-report"], ["--save-report"], ["--model-report", "--save-report"]):
                code, output, errors = self.call_main([
                    "--database", str(self.target), "--log-dir", str(self.root / "logs"), *options,
                ])
                self.assertEqual((code, output), (2, ""))
                self.assertIn("--database kann nicht mit", errors)
            importer.assert_not_called()
            save.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_without_database_output_and_filesystem_behavior_are_unchanged(self) -> None:
        """A plain call must not connect, hash an extra input or create output files."""
        with patch("sqlite_storage.sqlite3.connect") as connect, patch("cosi.save_analysis_run") as save:
            code, output, errors = self.call_main([])
            self.assertEqual((code, errors), (0, ""))
            connect.assert_not_called()
            save.assert_not_called()
        expected = ("Temperaturauswertung\nMesswerte insgesamt: 6\nGültige Messwerte: 5\n"
                    "Fehlende Messwerte: 1\nMinimum: 40.0 °C\nMaximum: 65.0 °C\n"
                    "Arithmetischer Mittelwert: 53.6 °C\nSchwellenwert: 60.0 °C\n"
                    "Werte strikt oberhalb des Schwellenwerts: 2\n")
        self.assertEqual(output, expected)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_failed_processing_does_not_create_database(self) -> None:
        """Analysis errors happen before storage, so no database directory appears."""
        with patch("cosi.analyze_temperatures", side_effect=ValueError("invalid measurements")):
            code, output, errors = self.call_main(["--database", str(self.target)])
        self.assertEqual((code, output), (1, ""))
        self.assertIn("invalid measurements", errors)
        self.assertFalse(self.target.parent.exists())

    def test_csv_changed_during_import_is_not_recorded_with_wrong_hash(self) -> None:
        """A changed input must fail before storing its original fingerprint."""
        source = self.root / "changing.csv"
        source.write_bytes(SAMPLE_PATH.read_bytes())
        original_importer = cosi.read_temperature_csv

        def change_after_import(path: str) -> list[dict[str, float | None]]:
            """Keep parsing real, then simulate another process changing the file."""
            records = original_importer(path)
            source.write_text("time_s,temperature_c\n0,99\n")
            return records

        with patch("cosi.read_temperature_csv", side_effect=change_after_import):
            with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
                code = cosi.main([str(source), "--database", str(self.target)])
        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue(), "")
        self.assertIn("während des Imports geändert", errors.getvalue())
        self.assertFalse(self.target.exists())

    def test_storage_error_suppresses_success_and_is_logged(self) -> None:
        """A database failure produces CLI code 1 and an error in the JSONL log."""
        for error in (SQLiteStorageError("test storage failure"), OSError("test disk failure")):
            with patch("cosi.save_analysis_run", side_effect=error):
                code, output, errors = self.call_main([
                    "--database", str(self.target), "--log-dir", str(self.root / "logs"),
                ])
            self.assertEqual((code, output), (1, ""))
            self.assertIn("Fehler beim Speichern in der Datenbank", errors)
        for path in (self.root / "logs").glob("*.jsonl"):
            events = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(events[-2]["step"], "database_save")
            self.assertEqual(events[-1]["status"], "error")

    def test_logging_uses_same_identity_and_late_logging_error_reports_saved_run(self) -> None:
        """Committed database rows remain valid if closing the separate log fails."""
        original_close = RunLogger.close

        def fail_after_close(logger: RunLogger) -> None:
            """Release the real log handle before simulating a reported close failure."""
            original_close(logger)
            raise RunLoggingError("simulated close failure")

        with patch.object(RunLogger, "close", fail_after_close):
            code, output, errors = self.call_main([
                "--database", str(self.target), "--log-dir", str(self.root / "logs"),
            ])
        self.assertEqual((code, output), (1, ""))
        self.assertIn("bereits in der Datenbank gespeichert", errors)
        events = [json.loads(line) for line in next((self.root / "logs").glob("*.jsonl")).read_text().splitlines()]
        self.assertEqual(self.snapshot()[0][0][0], events[0]["run_id"])


if __name__ == "__main__":
    unittest.main()
