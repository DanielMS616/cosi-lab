"""Prepare or explicitly execute the fixed prompt comparison without evaluating text."""

import argparse
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

from openai_text import OpenAITextError, generate_text
from temperature_analysis import analyze_temperatures
from temperature_csv import read_temperature_csv


REPO_DIR = Path(__file__).resolve().parent
VARIANT_COMMITS = {
    "A": "5e5037129eeeb116ec54c5df511873fbe5533586",
    "B": "261350f217008cadfd60aa47dfe210cd9881d9df",
}
REFERENCE_COMMIT = "a67dc34d12d221b3d1a61b3dd97c748e2f7a6219"
MODEL = "gpt-4.1-mini"
CASE_ORDER = ("threshold_equal", "mostly_missing", "all_above", "repeated_threshold")
RESULT_FIELDS = {"total_count", "valid_count", "missing_count", "minimum",
                 "maximum", "mean", "exceedance_count"}


def read_historical_text(commit: str, path: str) -> str:
    """Read a pinned Git object without checkout; this is the history test boundary."""
    try:
        completed = subprocess.run(
            ["git", "show", f"{commit}:{path}"], cwd=REPO_DIR,
            capture_output=True, check=True, encoding="utf-8",
        )
    except subprocess.CalledProcessError:
        raise ValueError(f"Historische Quelle nicht verfügbar: {commit}:{path}") from None
    return completed.stdout


def load_report_module(variant: str) -> ModuleType:
    """Execute the explicitly pinned, trusted project source in a separate namespace.

    ModuleType supplies a module dictionary. compile/exec loads the historical
    functions there without writing a Python file or replacing an imported module.
    This executes trusted repository code, never code supplied by a model.
    """
    commit = VARIANT_COMMITS[variant]
    source = read_historical_text(commit, "temperature_report.py")
    module = ModuleType(f"report_variant_{variant}")
    exec(compile(source, f"git:{commit}:temperature_report.py", "exec"), module.__dict__)
    return module


def load_validated_cases() -> dict:
    """Read pinned manifests and CSVs, validating every case before any model call."""
    cases = {}
    with tempfile.TemporaryDirectory() as directory:
        for manifest_name in ("cases.json", "control_cases.json"):
            prefix = "examples/report_eval/"
            entries = json.loads(read_historical_text(REFERENCE_COMMIT, prefix + manifest_name))
            for entry in entries:
                case_id = entry["case_id"]
                if case_id in cases:
                    raise ValueError("Doppelte Fall-ID im Referenzmanifest.")
                # Only local filenames from the pinned manifest enter the temp directory.
                filename = entry["csv_file"]
                if not filename or Path(filename).name != filename:
                    raise ValueError("Referenz-CSV muss ein einfacher Dateiname sein.")
                csv_text = read_historical_text(REFERENCE_COMMIT, prefix + filename)
                temporary_csv = Path(directory) / filename
                temporary_csv.write_text(csv_text, encoding="utf-8")
                records = read_temperature_csv(temporary_csv)
                facts = analyze_temperatures(
                    [record["temperature_c"] for record in records], entry["threshold"]
                )
                expected = entry["expected_result"]
                if set(expected) != RESULT_FIELDS or set(facts) != RESULT_FIELDS:
                    raise ValueError(f"Unvollständige Referenzkennzahlen: {case_id}")
                for field in RESULT_FIELDS:
                    value = expected[field]
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise ValueError(f"Ungültiger Sollwert: {case_id}, {field}")
                    matches = (math.isclose(facts[field], value, rel_tol=1e-9, abs_tol=1e-9)
                               if field == "mean" else facts[field] == value)
                    if not matches:
                        raise ValueError(f"Abweichung vom Sollwert: {case_id}, {field}")
                cases[case_id] = {"facts": facts, "threshold": entry["threshold"]}
    if not set(CASE_ORDER).issubset(cases):
        raise ValueError("Ein Vergleichsfall fehlt im Referenzmanifest.")
    return cases


def record_prompt(module: ModuleType, facts: dict, threshold: int | float) -> str:
    """Capture the historical function's exact prompt, discarding its dummy answer."""
    prompts: list[str] = []

    def recorder(prompt: str) -> str:
        """Stand in for a generator without contacting a model."""
        prompts.append(prompt)
        return "Nur interner Platzhalter; kein Modellergebnis."

    module.generate_temperature_report(dict(facts), threshold, recorder)
    if len(prompts) != 1 or not isinstance(prompts[0], str) or not prompts[0].strip():
        raise ValueError("Historische Berichtsfunktion muss genau einen Auftrag erzeugen.")
    return prompts[0]


def prepare_attempts(live: bool) -> list[dict]:
    """Validate all inputs and freeze the twelve alternating pairs as 24 records."""
    cases = load_validated_cases()
    modules = {variant: load_report_module(variant) for variant in VARIANT_COMMITS}
    attempts = []
    pair = 0
    for case_id in CASE_ORDER:
        case = cases[case_id]
        prompts = {variant: record_prompt(module, case["facts"], case["threshold"])
                   for variant, module in modules.items()}
        for repetition in range(1, 4):
            pair += 1
            variants = ("A", "B") if pair % 2 else ("B", "A")
            for variant in variants:
                attempts.append({
                    "schema_version": 1,
                    "variant_commits": dict(VARIANT_COMMITS),
                    "reference_commit": REFERENCE_COMMIT,
                    "model": MODEL,
                    "mode": "live" if live else "prepare",
                    "order": len(attempts) + 1,
                    "case_id": case_id,
                    "variant": variant,
                    "repetition": repetition,
                    "prompt": prompts[variant],
                    "event": "prepared",
                    "technical_status": "not_executed",
                    "response": None,
                    "error_type": None,
                })
    return attempts


def write_record(stream, record: dict) -> None:
    """Flush every complete UTF-8 JSON line before the next processing action."""
    stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()


def run_comparison(output_dir: Path, live: bool = False, text_generator=None) -> int:
    """Create a fresh external experiment; return the number of adapter failures.

    The injected generator is used only in live mode. Storage errors and user
    interruptions propagate immediately, so no further requests can start.
    Expected adapter errors are recorded without their message and never retried.
    """
    output_dir = output_dir.resolve()
    if output_dir.is_relative_to(REPO_DIR.resolve()):
        raise ValueError("Der Versuchsordner muss außerhalb des Repositorys liegen.")
    if output_dir.exists():
        raise ValueError("Der Versuchsordner existiert bereits; nichts wird überschrieben.")
    attempts = prepare_attempts(live)
    # All history reads, input checks, and prompt construction have succeeded.
    output_dir.mkdir(parents=True, exist_ok=False)
    with (output_dir / "plan.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for attempt in attempts:
            write_record(stream, attempt)
    if not live:
        return 0

    generator = generate_text if text_generator is None else text_generator
    failures = 0
    with (output_dir / "results.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for attempt in attempts:
            write_record(stream, {**attempt, "event": "attempt_started",
                                  "technical_status": "started"})
            try:
                response = generator(attempt["prompt"], model=MODEL)
            except OpenAITextError as error:
                failures += 1
                result = {**attempt, "event": "attempt_finished",
                          "technical_status": "error", "error_type": type(error).__name__}
            else:
                result = {**attempt, "event": "attempt_finished",
                          "technical_status": "success", "response": response}
            # Keep this outside the adapter-error handler: storage failure must stop.
            write_record(stream, result)
    return failures


def main(argv: list[str] | None = None) -> int:
    """Prepare by default; explicit --live authorizes at most 24 adapter calls."""
    parser = argparse.ArgumentParser(description="Festgelegten Promptvergleich vorbereiten oder ausführen.")
    parser.add_argument("--output-dir", required=True, type=Path, metavar="PATH",
                        help="Neuer Versuchsordner außerhalb des Repositorys.")
    parser.add_argument("--live", action="store_true",
                        help="API-Anfragen ausdrücklich aktivieren (sonst nur Vorbereitung).")
    args = parser.parse_args(argv)
    try:
        failures = run_comparison(args.output_dir, live=args.live)
    except KeyboardInterrupt:
        print("Abgebrochen; keine weiteren Anfragen. Vorhandene Nachweise bleiben erhalten.", file=sys.stderr)
        return 130
    except (OSError, ValueError) as error:
        print(f"Vergleich gestoppt: {error}. Keine weiteren Anfragen.", file=sys.stderr)
        return 1
    if not args.live:
        print("24 Versuche vorbereitet, nicht ausgeführt: plan.jsonl; keine Modellantworten.")
    else:
        print(f"Vergleich beendet: {failures} technische Fehler. Nachweise: plan.jsonl und results.jsonl.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
