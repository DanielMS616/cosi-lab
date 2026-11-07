"""Exercise real SQLite persistence offline with temporary files, not SQL mocks."""

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

import sqlite_demo
from sqlite_storage import SQLiteStorageError, open_database, save_demo_run
from temperature_report import generate_temperature_report


PROJECT_DIR = Path(__file__).resolve().parent.parent
QUERY = (PROJECT_DIR / "db/demo_query.sql").read_text(encoding="utf-8")


class SQLiteDemoTests(unittest.TestCase):
    """Verify persisted evidence and path protection, not API/model quality."""

    def setUp(self) -> None:
        """Isolate output, remove credentials and make network access fail the test."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.target = self.root / "data/demo.sqlite3"
        for boundary in (
            patch.dict(os.environ, {}, clear=True),
            patch("socket.create_connection", side_effect=AssertionError("No network in demo.")),
            patch("openai_text.http.client.HTTPSConnection", side_effect=AssertionError("No API in demo.")),
        ):
            boundary.start()
            self.addCleanup(boundary.stop)

    def test_reopened_database_joins_input_analysis_call_and_report(self) -> None:
        """A real run must round-trip its full evidence with correct links and hashes."""
        with chdir(self.root):
            run_id = sqlite_demo.run_demo(self.target)
        # run_demo already closed the writer; this is a separate connection.
        with closing(open_database(self.target)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(QUERY).fetchall()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["status"], "succeeded")
            self.assertEqual(row["simulation"], 1)
            self.assertEqual(Path(row["csv_path"]), sqlite_demo.SAMPLE_PATH)
            analysis = json.loads(row["analysis_json"])
            self.assertEqual(analysis, {
                "total_count": 6, "valid_count": 5, "missing_count": 1,
                "minimum": 40.0, "maximum": 65.0, "mean": 53.6, "exceedance_count": 2,
            })
            result = sqlite_demo.SIMULATED_RESULT
            for column, expected in (
                ("provider", "simulation"), ("model_requested", result.requested_model),
                ("model_returned", result.returned_model), ("response_id", result.response_id),
                ("request_id", result.request_id), ("input_tokens", result.input_tokens),
                ("output_tokens", result.output_tokens), ("total_tokens", result.total_tokens),
                ("duration_ms", result.duration_ms), ("http_status", None),
                ("response_json", None), ("report", result.text), ("report_matches_response", 1),
            ):
                self.assertEqual(row[column], expected, column)
            call = connection.execute("SELECT * FROM model_calls WHERE run_id = ?", (run_id,)).fetchone()
            captured = []

            def capture_prompt(prompt: str) -> str:
                """Capture the current report function's prompt for exact comparison."""
                captured.append(prompt)
                return result.text

            generate_temperature_report(analysis, sqlite_demo.THRESHOLD, capture_prompt)
            self.assertEqual(call["prompt_text"], captured[0])
            self.assertEqual(call["prompt_sha256"], hashlib.sha256(captured[0].encode()).hexdigest())
            request = json.loads(call["request_json"])
            self.assertTrue(request["simulation"])
            self.assertEqual(request["input"], captured[0])
            self.assertEqual(call["response_headers_json"], "{}")
            self.assertIsNone(call["response_status"])
            self.assertIsNone(call["usage_json"])
            for artifact in connection.execute("SELECT * FROM artifacts"):
                if artifact["kind"] == "input_file":
                    content = sqlite_demo.SAMPLE_PATH.read_bytes()
                    self.assertIsNone(artifact["content_text"])
                else:
                    content = artifact["content_text"].encode("utf-8")
                self.assertEqual(artifact["byte_count"], len(content))
                self.assertEqual(artifact["content_sha256"], hashlib.sha256(content).hexdigest())
            for table, count in (("runs", 1), ("artifacts", 3), ("model_calls", 1),
                                 ("approvals", 0), ("exports", 0)):
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], count)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(sorted(p.relative_to(self.root).as_posix()
                                for p in self.root.rglob("*") if p.is_file()), ["data/demo.sqlite3"])

    def test_each_connection_enables_foreign_keys_and_recursive_triggers(self) -> None:
        """Reopened connections must enforce references and immutable evidence."""
        run_id = sqlite_demo.run_demo(self.target)
        for _ in range(2):
            with closing(open_database(self.target)) as connection:
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertEqual(connection.execute("PRAGMA recursive_triggers").fetchone()[0], 1)
                with self.assertRaises(sqlite3.IntegrityError):
                    with connection:
                        connection.execute("INSERT OR REPLACE INTO runs SELECT * FROM runs WHERE run_id = ?", (run_id,))
                # A valid event except for its nonexistent run tests FK enforcement.
                with self.assertRaises(sqlite3.IntegrityError):
                    with connection:
                        connection.execute(
                            """INSERT INTO run_events (run_id, sequence_no, occurred_at, event_type)
                               VALUES ('missing', 1, '2026-11-07T00:00:00.000000Z', 'test')"""
                        )

    def test_existing_file_or_database_is_never_overwritten(self) -> None:
        """Both arbitrary bytes and a prior demo database must remain byte-identical."""
        self.target.parent.mkdir()
        self.target.write_bytes(b"existing file\x00")
        for existing_database in (False, True):
            if existing_database:
                self.target.unlink()
                sqlite_demo.run_demo(self.target)
            original = self.target.read_bytes()
            with self.assertRaises(FileExistsError):
                sqlite_demo.run_demo(self.target)
            self.assertEqual(self.target.read_bytes(), original)

    def test_directory_and_dangling_symlink_are_rejected(self) -> None:
        """Exclusive creation must not follow a preexisting dangling link."""
        self.target.parent.mkdir()
        self.target.mkdir()
        with self.assertRaises(FileExistsError):
            sqlite_demo.run_demo(self.target)
        self.target.rmdir()
        destination = self.root / "must-not-be-created"
        self.target.symlink_to(destination)
        with self.assertRaises(FileExistsError):
            sqlite_demo.run_demo(self.target)
        self.assertFalse(destination.exists())

    def test_failed_insert_rolls_back_all_run_evidence(self) -> None:
        """A schema constraint failure late in storage must not leave half a run."""
        with patch("sqlite_demo.save_demo_run", return_value="captured") as save:
            sqlite_demo.run_demo(self.target)
        run = save.call_args.args[1]
        invalid_result = replace(run.model_result, total_tokens=999)
        with self.assertRaises(SQLiteStorageError):
            save_demo_run(self.target, replace(run, model_result=invalid_result))
        with closing(open_database(self.target)) as connection:
            for table in ("runs", "artifacts", "model_calls"):
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)

    def test_cli_requires_path_and_reports_success_or_existing_path(self) -> None:
        """The separate demo command accepts no implicit output and never exports."""
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(sqlite_demo.main(["--database", str(self.target)]), 0)
            self.assertIn("Simulation gespeichert", output.getvalue())
            output.seek(0)
            output.truncate()
            self.assertEqual(sqlite_demo.main(["--database", str(self.target)]), 1)
            self.assertEqual(output.getvalue(), "")
            self.assertIn("Demolauf fehlgeschlagen", errors.getvalue())
            with self.assertRaises(SystemExit) as caught:
                sqlite_demo.main([])
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
