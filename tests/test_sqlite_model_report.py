"""Verify the two committed model-call phases using real SQLite and fake models."""

import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import cosi
from openai_text import OpenAITextError, OpenAITextResult
from sqlite_storage import complete_model_run, fail_model_run, open_database, prepare_model_run


PROJECT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_PATH = PROJECT_DIR / "examples/temperature_sample.csv"
QUERY = (PROJECT_DIR / "db/model_calls_query.sql").read_text(encoding="utf-8")
SIMULATED_RESULT = OpenAITextResult(
    text="Simulierter Temperaturbericht.", requested_model="test-model",
    returned_model="test-model-snapshot", response_id="resp_simulated", request_id="req_simulated",
    input_tokens=10, output_tokens=4, total_tokens=14, duration_ms=37.5,
)


class SQLiteModelReportTests(unittest.TestCase):
    """Keep SQL, CLI and prompt construction real; replace only the adapter call."""

    def setUp(self) -> None:
        """Isolate files/credentials and block every real model/network request."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.target = Path(directory.name) / "model-runs.sqlite3"
        boundaries = (
            patch.dict(os.environ, {}, clear=True),
            patch("socket.create_connection", side_effect=AssertionError("No network in tests.")),
            patch("openai_text.http.client.HTTPSConnection", side_effect=AssertionError("No HTTP in tests.")),
            patch("cosi.generate_text", side_effect=AssertionError("Use the typed adapter with a database.")),
        )
        for boundary in boundaries:
            boundary.start()
            self.addCleanup(boundary.stop)
        model = patch("cosi.generate_text_result")
        self.model = model.start()
        self.addCleanup(model.stop)

    def call_main(self) -> tuple[int, str, str]:
        """Call the normal CLI with the database, model-report and model options."""
        with redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()) as errors:
            code = cosi.main([str(SAMPLE_PATH), "--database", str(self.target),
                              "--model-report", "--model", "test-model"])
        return code, output.getvalue(), errors.getvalue()

    def assert_start_visible(self, prompt: str, *, model: str) -> None:
        """A separate connection sees the committed real prompt before the fake API."""
        self.assertEqual(model, "test-model")
        with closing(open_database(self.target)) as connection:
            # A second writer can acquire a lock: preparation left no transaction open.
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT r.status, m.status, m.prompt_text, m.request_json, m.prompt_sha256,
                              r.finished_at, m.finished_at, m.response_text
                       FROM runs r JOIN model_calls m ON r.run_id = m.run_id
                       WHERE m.status = 'started'"""
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[:3], ("running", "started", prompt))
                self.assertEqual(json.loads(row[3]), {
                    "model": "test-model", "input": prompt, "max_output_tokens": 600, "store": False,
                })
                self.assertEqual(row[4], hashlib.sha256(prompt.encode()).hexdigest())
                self.assertEqual(row[5:], (None, None, None))
                kinds = connection.execute(
                    """SELECT a.kind FROM artifacts a JOIN runs r ON r.run_id = a.run_id
                       WHERE r.status = 'running' ORDER BY a.kind"""
                ).fetchall()
                self.assertEqual(kinds, [("analysis",), ("input_file",)])
                facts = json.loads(prompt.split("Kennzahlen (JSON):\n")[1])
                self.assertEqual((facts["mean"], facts["threshold"]), (53.6, 60.0))

    def test_success_and_http_429_leave_queryable_outcomes_in_same_database(self) -> None:
        """Success has a linked report; a later 429 has safe diagnostics and no report."""
        def succeed(prompt: str, *, model: str) -> OpenAITextResult:
            self.assert_start_visible(prompt, model=model)
            return SIMULATED_RESULT

        self.model.side_effect = succeed
        code, output, errors = self.call_main()
        self.assertEqual((code, errors), (0, ""))
        self.model.assert_called_once()
        with closing(open_database(self.target)) as connection:
            connection.row_factory = sqlite3.Row
            call = connection.execute("SELECT * FROM model_calls").fetchone()
            for name, expected in (
                ("status", "succeeded"), ("provider", "openai"),
                ("model_requested", "test-model"), ("model_returned", "test-model-snapshot"),
                ("response_id", "resp_simulated"), ("request_id", "req_simulated"),
                ("response_text", SIMULATED_RESULT.text), ("input_tokens", 10),
                ("output_tokens", 4), ("total_tokens", 14), ("duration_ms", 37.5),
                ("response_headers_json", "{}"),
            ):
                self.assertEqual(call[name], expected, name)
            for name in ("http_status", "response_status", "response_json", "server_processing_ms",
                         "provider_created_at", "provider_completed_at", "cached_input_tokens",
                         "reasoning_output_tokens", "usage_json", "error_code",
                         "provider_error_code", "provider_error_type"):
                self.assertIsNone(call[name], name)
            report = connection.execute("SELECT * FROM artifacts WHERE kind = 'report'").fetchone()
            self.assertEqual(report["content_text"], output)
            self.assertEqual(report["model_call_id"], call["call_id"])
            self.assertEqual(report["source_artifact_id"], call["input_artifact_id"])

        def fail(prompt: str, *, model: str) -> OpenAITextResult:
            self.assert_start_visible(prompt, model=model)
            raise OpenAITextError("private-error-marker", error_code="http_error", http_status=429)

        self.model.reset_mock()
        self.model.side_effect = fail
        code, output, errors = self.call_main()
        self.assertEqual((code, output), (1, ""))
        self.assertIn("Fehler bei der Modellberichterstellung", errors)
        self.model.assert_called_once()
        with closing(open_database(self.target)) as connection:
            rows = connection.execute(QUERY).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual((rows[0][1:5], rows[0][-1]), (("succeeded", "succeeded", None, None), 1))
            self.assertEqual((rows[1][1:5], rows[1][-1]), (("failed", "failed", "http_error", 429), 0))
            failed = connection.execute("SELECT status, error_code, finished_at, duration_ms FROM runs WHERE status = 'failed'").fetchone()
            self.assertEqual(failed[:2], ("failed", "http_error"))
            self.assertIsNotNone(failed[2])
            self.assertGreaterEqual(failed[3], 0)
            self.assertNotIn("private-error-marker", "\n".join(connection.iterdump()))
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_missing_metadata_and_unknown_error_http_status_stay_null(self) -> None:
        """Missing optional result fields and a timeout status must never be inferred."""
        self.model.return_value = replace(
            SIMULATED_RESULT, returned_model=None, response_id=None, request_id=None,
            input_tokens=None, output_tokens=None, total_tokens=None,
        )
        self.assertEqual(self.call_main()[0], 0)
        self.model.side_effect = OpenAITextError("timeout", error_code="timeout")
        self.assertEqual(self.call_main()[0], 1)
        with closing(open_database(self.target)) as connection:
            rows = connection.execute(
                """SELECT model_returned, response_id, request_id, input_tokens,
                          output_tokens, total_tokens, http_status FROM model_calls"""
            ).fetchall()
            self.assertEqual(rows, [(None,) * 7, (None,) * 7])

    def test_incompatible_database_prevents_request_and_stays_unchanged(self) -> None:
        """Foreign, future-version and changed-schema files fail before the adapter."""
        for case in ("foreign", "future", "changed"):
            with self.subTest(case=case):
                self.target.unlink(missing_ok=True)
                with closing(sqlite3.connect(self.target)) as connection:
                    if case == "foreign":
                        connection.execute("CREATE TABLE foreign_data (value TEXT)")
                    else:
                        connection.executescript((PROJECT_DIR / "db/schema.sql").read_text())
                        if case == "future":
                            connection.execute("PRAGMA user_version = 99")
                        else:
                            connection.execute("DROP TRIGGER artifacts_deny_delete")
                original = self.target.read_bytes()
                code, output, errors = self.call_main()
                self.assertEqual((code, output), (1, ""))
                self.assertIn("Datenbank", errors)
                self.assertEqual(self.target.read_bytes(), original)
                self.model.assert_not_called()

    def test_preparation_constraint_failure_rolls_back_and_prevents_request(self) -> None:
        """A late start-INSERT failure must not leave any run/input/analysis rows."""
        def invalid_prompt(path, run, **options):
            options["prompt"] = ""
            return prepare_model_run(path, run, **options)

        with patch("cosi.prepare_model_run", side_effect=invalid_prompt):
            code, output, errors = self.call_main()
        self.assertEqual((code, output), (1, ""))
        self.assertIn("Speichern in der Datenbank", errors)
        self.model.assert_not_called()
        with closing(open_database(self.target)) as connection:
            for table in ("runs", "artifacts", "model_calls"):
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)

    def test_success_finalization_failure_rolls_back_without_repeating_request(self) -> None:
        """Fail the last run UPDATE after call/report writes; start evidence survives."""
        self.model.return_value = SIMULATED_RESULT

        def invalid_run_duration(path, call, **options):
            options["run_duration_ms"] = -1.0
            return complete_model_run(path, call, **options)

        with patch("cosi.complete_model_run", side_effect=invalid_run_duration):
            code, output, errors = self.call_main()
        self.assertEqual((code, output), (1, ""))
        self.assertIn("Speichern in der Datenbank", errors)
        self.model.assert_called_once()
        self.assert_pending_without_report()

    def test_error_finalization_failure_reports_storage_error_without_retry(self) -> None:
        """Even a 429 cannot trigger a second request if recording its failure fails."""
        self.model.side_effect = OpenAITextError("simulated 429", error_code="http_error", http_status=429)

        def invalid_run_duration(path, call, **options):
            options["run_duration_ms"] = -1.0
            return fail_model_run(path, call, **options)

        with patch("cosi.fail_model_run", side_effect=invalid_run_duration):
            code, output, errors = self.call_main()
        self.assertEqual((code, output), (1, ""))
        self.assertIn("Speichern in der Datenbank", errors)
        self.assertNotIn("Fehler bei der Modellberichterstellung", errors)
        self.model.assert_called_once()
        self.assert_pending_without_report()

    def assert_pending_without_report(self) -> None:
        """Both lifecycle rows and the artifact count retain their committed starts."""
        with closing(open_database(self.target)) as connection:
            self.assertEqual(connection.execute("SELECT status, finished_at FROM runs").fetchall(), [("running", None)])
            self.assertEqual(connection.execute("SELECT status, response_text, error_code FROM model_calls").fetchall(),
                             [("started", None, None)])
            self.assertEqual(connection.execute("SELECT kind FROM artifacts ORDER BY kind").fetchall(),
                             [("analysis",), ("input_file",)])

    def test_model_report_without_database_keeps_using_legacy_text_interface(self) -> None:
        """No-database callers keep their text-only adapter and need no SQLite."""
        with patch("cosi.generate_text", return_value="legacy text") as legacy:
            with patch("sqlite_storage.sqlite3.connect") as connect:
                with redirect_stdout(io.StringIO()) as output:
                    code = cosi.main([str(SAMPLE_PATH), "--model-report"])
        self.assertEqual(code, 0)
        self.assertIn("legacy text", output.getvalue())
        legacy.assert_called_once()
        self.model.assert_not_called()
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
