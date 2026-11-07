"""Run the existing temperature pipeline offline and save one SQLite simulation."""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from openai_text import OpenAITextResult
from run_record import CompletedRun
from sqlite_storage import SQLiteStorageError, save_demo_run
from temperature_analysis import analyze_temperatures
from temperature_csv import read_temperature_csv
from temperature_report import generate_temperature_report


SAMPLE_PATH = Path(__file__).resolve().parent / "examples/temperature_sample.csv"
THRESHOLD = 60.0
SIMULATED_RESULT = OpenAITextResult(
    text=("Simulation: Von 6 Messwerten sind 5 gültig und 1 fehlt. "
          "Der fehlende Wert wurde nicht ersetzt und nicht in die Berechnung einbezogen. "
          "Minimum: 40,0 °C; Maximum: 65,0 °C; Mittelwert: 53,6 °C. "
          "2 Werte liegen strikt über dem Schwellenwert von 60,0 °C. "
          "Gleichheit zählt nicht als Überschreitung."),
    requested_model="simulated-openai-text", returned_model="simulated-openai-text-v1",
    response_id="simulated-response-demo", request_id="simulated-request-demo",
    input_tokens=100, output_tokens=40, total_tokens=140, duration_ms=12.5,
)


def _utc_now() -> str:
    """Return the schema's fixed-width UTC representation with microseconds."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class SimulatedGenerator:
    """Capture the real report prompt and supply explicit synthetic metadata."""

    def __init__(self) -> None:
        """Start without a captured prompt or call timestamps."""
        self.prompt: str | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.result: OpenAITextResult | None = None

    def generate_result(self, prompt: str) -> OpenAITextResult:
        """Record one invocation and return a fixed result without any API access."""
        if self.prompt is not None:
            raise ValueError("The demo allows exactly one simulated model call.")
        self.started_at = _utc_now()
        self.prompt = prompt
        self.result = SIMULATED_RESULT
        self.finished_at = _utc_now()
        return self.result

    def generate_text(self, prompt: str) -> str:
        """Bridge the typed simulation to the existing report function's str API."""
        return self.generate_result(prompt).text


def run_demo(database_path: str | Path) -> str:
    """Compute the sample with existing functions and pass evidence to storage.

    Keep SQL and connections outside orchestration. The demo uses only the
    packaged synthetic CSV and a fixed threshold/result, never an API key.
    Run timing excludes database writing; model timing/tokens/IDs are synthetic.
    """
    started_at = _utc_now()
    started_counter = time.perf_counter()
    input_bytes = SAMPLE_PATH.read_bytes()
    records = read_temperature_csv(SAMPLE_PATH)
    values = [record["temperature_c"] for record in records]
    analysis = analyze_temperatures(values, threshold=THRESHOLD)
    generator = SimulatedGenerator()
    report = generate_temperature_report(analysis, THRESHOLD, generator.generate_text)
    if (generator.prompt is None or generator.started_at is None
            or generator.finished_at is None or generator.result is None):
        raise ValueError("The report did not invoke the simulated generator.")
    run = CompletedRun(
        input_path=SAMPLE_PATH, input_bytes=input_bytes, analysis=analysis,
        threshold=THRESHOLD, prompt=generator.prompt, model_result=generator.result,
        report=report, started_at=started_at, finished_at=_utc_now(),
        duration_ms=(time.perf_counter() - started_counter) * 1000,
        model_started_at=generator.started_at, model_finished_at=generator.finished_at,
    )
    return save_demo_run(database_path, run)


def main(argv: list[str] | None = None) -> int:
    """Require an explicit new database path; report errors without a success claim."""
    parser = argparse.ArgumentParser(description="SQLite-Demolauf mit simuliertem Modell, vollständig offline.")
    parser.add_argument("--database", required=True, type=Path, help="Neu anzulegender Datenbankpfad, z. B. data/demo.sqlite3")
    args = parser.parse_args(argv)
    try:
        run_id = run_demo(args.database)
    except (OSError, ValueError, SQLiteStorageError) as error:
        print(f"Demolauf fehlgeschlagen: {error}", file=sys.stderr)
        return 1
    print(f"Simulation gespeichert: {args.database} (run_id={run_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
