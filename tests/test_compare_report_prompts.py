"""Check comparison orchestration offline, replacing history and model boundaries."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import compare_report_prompts as comparison
from openai_text import OpenAITextError


# These small fake historical modules test loading and forwarding, not prompt quality.
# They are deliberately not copies of the real A/B prompt implementations.
FAKE_SOURCE = '''
import json
def generate_temperature_report(facts, threshold, generator):
    prompt = PREFIX + json.dumps({"facts": facts, "threshold": threshold}, ensure_ascii=False)
    return generator(prompt)
'''
FIELD_NAMES = ("total_count", "valid_count", "missing_count", "minimum",
               "maximum", "mean", "exceedance_count")
FIXTURES = [
    ("threshold_equal", "0,40\n10,50\n20,60\n", 60, (3, 3, 0, 40, 60, 50, 0)),
    ("mostly_missing", "0,\n10,40\n20,\n30,\n40,60\n50,\n60,\n70,65\n", 60,
     (8, 3, 5, 40, 65, 55, 1)),
    ("single_valid", "0,\n10,42\n20,\n", 60, (3, 1, 2, 42, 42, 42, 0)),
    ("negative_temperatures", "0,-15\n10,-10\n20,-5\n30,\n40,0\n", -5,
     (5, 4, 1, -15, 0, -7.5, 1)),
    ("all_above", "0,12\n10,18\n20,\n30,24\n", 10, (4, 3, 1, 12, 24, 18, 3)),
    ("repeated_threshold", "0,10\n10,20\n20,\n30,20\n40,30\n50,40\n", 20,
     (6, 5, 1, 10, 40, 24, 2)),
]


class CompareReportPromptsTests(unittest.TestCase):
    """Use actual temporary JSONL files and computation, with no Git history needed."""

    def setUp(self) -> None:
        """Supply independent, pinned-source fixtures and forbid real API access."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.output = self.root / "experiment"
        self.sources = {}
        entries = []
        for case_id, rows, threshold, statistics in FIXTURES:
            entries.append({"case_id": case_id, "csv_file": case_id + ".csv",
                            "threshold": threshold,
                            "expected_result": dict(zip(FIELD_NAMES, statistics))})
            self.sources[(comparison.REFERENCE_COMMIT, "examples/report_eval/" + case_id + ".csv")] = (
                "time_s,temperature_c\n" + rows
            )
        for filename, cases in (("cases.json", entries[:4]), ("control_cases.json", entries[4:])):
            self.sources[(comparison.REFERENCE_COMMIT, "examples/report_eval/" + filename)] = json.dumps(cases)
        for variant, commit in comparison.VARIANT_COMMITS.items():
            self.sources[(commit, "temperature_report.py")] = (
                "PREFIX = " + repr(variant + " original\nGrüße: ") + "\n" + FAKE_SOURCE
            )
        self.history_patch = patch("compare_report_prompts.read_historical_text", side_effect=self.read_source)
        self.history = self.history_patch.start()
        self.addCleanup(self.history_patch.stop)
        generator = patch("compare_report_prompts.generate_text",
                          side_effect=AssertionError("Real adapter must not run in tests."))
        self.adapter = generator.start()
        self.addCleanup(generator.stop)

    def read_source(self, commit: str, path: str) -> str:
        """Serve fake Git objects; missing objects fail without consulting real Git."""
        try:
            return self.sources[(commit, path)]
        except KeyError:
            raise ValueError("Missing historical fixture.") from None

    def records(self, filename: str) -> list[dict]:
        """Parse complete JSONL records after a run, including partial runs."""
        text = (self.output / filename).read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        return [json.loads(line) for line in text.splitlines()]

    def call_main(self, options: list[str]) -> tuple[int, str, str]:
        """Capture the real CLI handler without spawning a process or reaching Git."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = comparison.main(["--output-dir", str(self.output), *options])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_exact_prepared_schedule_and_provenance(self) -> None:
        """Verify all 24 identities against the plan's alternating twelve pairs."""
        comparison.run_comparison(self.output)
        records = self.records("plan.jsonl")
        pairs = [
            ("threshold_equal", 1, "AB"), ("threshold_equal", 2, "BA"),
            ("threshold_equal", 3, "AB"), ("mostly_missing", 1, "BA"),
            ("mostly_missing", 2, "AB"), ("mostly_missing", 3, "BA"),
            ("all_above", 1, "AB"), ("all_above", 2, "BA"), ("all_above", 3, "AB"),
            ("repeated_threshold", 1, "BA"), ("repeated_threshold", 2, "AB"),
            ("repeated_threshold", 3, "BA"),
        ]
        expected = [(case, variant, repetition) for case, repetition, variants in pairs
                    for variant in variants]
        self.assertEqual([(r["case_id"], r["variant"], r["repetition"]) for r in records], expected)
        self.assertEqual([r["order"] for r in records], list(range(1, 25)))
        for record in records:
            self.assertEqual(record["schema_version"], 2)
            self.assertEqual(record["variant_commits"], comparison.VARIANT_COMMITS)
            self.assertEqual(record["reference_commit"], comparison.REFERENCE_COMMIT)
            self.assertEqual(record["model"], "gpt-4.1-mini")
            self.assertEqual(record["technical_status"], "not_executed")
            self.assertEqual(record["mode"], "prepare")
            self.assertIsNone(record["response"])
            self.assertIsNone(record["error_code"])
            self.assertIsNone(record["http_status"])
        self.adapter.assert_not_called()

    def test_historical_functions_receive_identical_facts_and_preserve_prompts(self) -> None:
        """Use distinguishable fake modules to detect wrong variants or rewritten text."""
        comparison.run_comparison(self.output)
        for record in self.records("plan.jsonl"):
            _, _, threshold, statistics = next(f for f in FIXTURES if f[0] == record["case_id"])
            expected_facts = dict(zip(FIELD_NAMES, statistics))
            # CSV import converts temperatures to float, including extrema and mean.
            for field in ("minimum", "maximum", "mean"):
                expected_facts[field] = float(expected_facts[field])
            expected = record["variant"] + " original\nGrüße: " + json.dumps({
                "facts": expected_facts, "threshold": threshold,
            }, ensure_ascii=False)
            self.assertEqual(record["prompt"], expected)
            self.assertNotIn("Platzhalter", record["prompt"])
        first = comparison.load_report_module("A")
        second = comparison.load_report_module("B")
        self.assertIsNot(first, second)
        self.assertNotEqual(first.PREFIX, second.PREFIX)

    def test_default_cli_never_calls_generator_even_with_key(self) -> None:
        """Preparation remains offline even when credentials are present."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret-marker"}):
            code, stdout, stderr = self.call_main([])
        self.assertEqual(code, 0)
        self.assertIn("nicht ausgeführt", stdout)
        self.assertEqual(stderr, "")
        self.adapter.assert_not_called()
        self.assertFalse((self.output / "results.jsonl").exists())
        self.assertNotIn("test-secret-marker", (self.output / "plan.jsonl").read_text())

    def test_live_starts_are_flushed_before_calls_and_responses_preserved(self) -> None:
        """Each fake live call observes its real start record and the previous result."""
        responses = []

        def generator(prompt: str, *, model: str) -> str:
            records = self.records("results.jsonl")
            self.assertEqual(len(records), len(responses) * 2 + 1)
            self.assertEqual(records[-1]["event"], "attempt_started")
            self.assertEqual(records[-1]["prompt"], prompt)
            self.assertEqual(model, "gpt-4.1-mini")
            response = f"  Antwort {len(responses)}: Grüße.\r\n  "
            responses.append(response)
            return response

        self.assertEqual(comparison.run_comparison(self.output, live=True, text_generator=generator), 0)
        records = self.records("results.jsonl")
        plan = self.records("plan.jsonl")
        self.assertEqual(len(records), 48)
        for record in records:
            self.assertEqual(record["schema_version"], 2)
            self.assertIsNone(record["error_code"])
            self.assertIsNone(record["http_status"])
        self.assertEqual([r["response"] for r in records[1::2]], responses)
        for index, record in enumerate(records[1::2]):
            self.assertEqual(record["prompt"], plan[index]["prompt"])
            self.assertEqual(record["order"], index + 1)
            self.assertEqual(record["technical_status"], "success")
            self.assertEqual(record["mode"], "live")
        self.adapter.assert_not_called()

    def test_adapter_errors_continue_without_replacement_or_message_leaks(self) -> None:
        """Failures with structured or legacy diagnostics occupy their slots without retries."""
        errors = {
            1: OpenAITextError("private-error-marker Authorization test-secret-marker",
                               error_code="http_error", http_status=429),
            9: OpenAITextError("private-error-marker", error_code="timeout"),
            15: OpenAITextError("legacy-error-marker"),
        }
        generator = Mock(side_effect=[errors.get(i, f"response-{i}") for i in range(24)])
        self.assertEqual(comparison.run_comparison(self.output, live=True, text_generator=generator), 3)
        results = self.records("results.jsonl")[1::2]
        plan = self.records("plan.jsonl")
        self.assertEqual(generator.call_count, 24)
        self.assertEqual([call.args[0] for call in generator.call_args_list], [r["prompt"] for r in plan])
        self.assertEqual([r["order"] for r in results if r["technical_status"] == "error"], [2, 10, 16])
        for index, code, status in ((1, "http_error", 429), (9, "timeout", None), (15, "unknown", None)):
            record = results[index]
            self.assertEqual(record["error_type"], "OpenAITextError")
            self.assertEqual(record["error_code"], code)
            self.assertEqual(record["http_status"], status)
            self.assertIsNone(record["response"])
        for record in self.records("results.jsonl"):
            self.assertEqual(record["schema_version"], 2)
            if record["technical_status"] != "error":
                self.assertIsNone(record["error_code"])
                self.assertIsNone(record["http_status"])
        self.assertEqual(results[-1]["response"], "response-23")
        for filename in ("plan.jsonl", "results.jsonl"):
            content = (self.output / filename).read_text()
            for marker in ("private-error-marker", "legacy-error-marker", "Authorization", "test-secret-marker"):
                self.assertNotIn(marker, content)

    def test_cli_live_uses_existing_adapter_and_failure_exit_code(self) -> None:
        """Patch the adapter name rather than requiring credentials or a server."""
        self.adapter.side_effect = [OpenAITextError("test")] + ["answer"] * 23
        code, stdout, stderr = self.call_main(["--live"])
        self.assertEqual(code, 1)
        self.assertIn("1 technische Fehler", stdout)
        self.assertEqual(stderr, "")
        self.assertEqual(self.adapter.call_count, 24)

    def test_invalid_reference_prevents_all_calls_and_output_creation(self) -> None:
        """Validate even reference cases not selected for the comparison before starting."""
        key = (comparison.REFERENCE_COMMIT, "examples/report_eval/negative_temperatures.csv")
        self.sources[key] = "time_s,temperature_c\n0,100\n"
        with self.assertRaises(ValueError):
            comparison.run_comparison(self.output, live=True)
        self.adapter.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_invalid_csv_or_missing_history_prevents_all_calls(self) -> None:
        """Input-format and history failures abort preflight, before creating output."""
        key = (comparison.REFERENCE_COMMIT, "examples/report_eval/all_above.csv")
        self.sources[key] = "wrong,header\n"
        with self.assertRaises(ValueError):
            comparison.run_comparison(self.output, live=True)
        del self.sources[key]
        with self.assertRaises(ValueError):
            comparison.run_comparison(self.output, live=True)
        self.adapter.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_existing_output_and_repository_paths_are_rejected(self) -> None:
        """Do not touch earlier experiments or allow output inside the repository."""
        self.output.mkdir()
        marker = self.output / "plan.jsonl"
        marker.write_text("existing evidence", encoding="utf-8")
        for path in (self.output, comparison.REPO_DIR / "comparison-output"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    comparison.run_comparison(path, live=True)
        self.assertEqual(marker.read_text(), "existing evidence")
        self.adapter.assert_not_called()
        self.history.assert_not_called()

    def test_symlink_into_repository_is_rejected(self) -> None:
        """Resolve parent symlinks before deciding whether a destination is external."""
        link = self.root / "repo-link"
        link.symlink_to(comparison.REPO_DIR, target_is_directory=True)
        with self.assertRaises(ValueError):
            comparison.run_comparison(link / "comparison-output", live=True)
        self.adapter.assert_not_called()

    def test_storage_errors_stop_before_any_next_call(self) -> None:
        """Fail preparation, a start, or a result while preserving earlier real lines."""
        original = comparison.write_record
        for event, order, expected_calls in (("prepared", 2, 0),
                                             ("attempt_started", 3, 2),
                                             ("attempt_finished", 2, 2)):
            with self.subTest(event=event):
                self.output = self.root / event
                generator = Mock(return_value="preserved answer")

                def write_or_fail(stream, record):
                    if (record["event"], record["order"]) == (event, order):
                        raise OSError("simulated storage failure")
                    return original(stream, record)

                with patch("compare_report_prompts.write_record", side_effect=write_or_fail):
                    with self.assertRaises(OSError):
                        comparison.run_comparison(self.output, live=True, text_generator=generator)
                self.assertEqual(generator.call_count, expected_calls)
                if expected_calls:
                    records = self.records("results.jsonl")
                    self.assertEqual(records[1]["response"], "preserved answer")

    def test_write_and_flush_errors_propagate(self) -> None:
        """Both file operations must succeed before another API call is permitted."""
        for operation in ("write", "flush"):
            stream = Mock()
            getattr(stream, operation).side_effect = OSError("storage failure")
            with self.assertRaises(OSError):
                comparison.write_record(stream, {"event": "test"})

    def test_user_interrupt_keeps_previous_answers_and_stops(self) -> None:
        """An interrupted third request leaves two results and an unfinished start."""
        self.adapter.side_effect = ["first", "second", KeyboardInterrupt()]
        code, stdout, stderr = self.call_main(["--live"])
        self.assertEqual(code, 130)
        self.assertEqual(stdout, "")
        self.assertIn("Abgebrochen", stderr)
        self.assertEqual(self.adapter.call_count, 3)
        records = self.records("results.jsonl")
        self.assertEqual(len(records), 5)
        self.assertEqual([records[1]["response"], records[3]["response"]], ["first", "second"])
        self.assertEqual(records[-1]["technical_status"], "started")

    def test_git_boundary_runs_show_without_checkout(self) -> None:
        """Test command construction without requiring any actual Git objects."""
        self.history_patch.stop()
        # The test normally fakes history. Here only subprocess.run is replaced.
        with patch("compare_report_prompts.subprocess.run", return_value=SimpleNamespace(stdout="source")) as run:
            self.assertEqual(comparison.read_historical_text("commit", "module.py"), "source")
        self.assertEqual(run.call_args.args[0], ["git", "show", "commit:module.py"])
        self.assertTrue(run.call_args.kwargs["check"])
