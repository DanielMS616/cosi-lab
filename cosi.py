"""Provide temperature analysis with an explicitly requested optional model report."""

import argparse
import math
import sys

from openai_text import OpenAITextError, generate_text
from run_logging import RunLoggingError, log_run, log_step
from temperature_analysis import analyze_temperatures
from temperature_csv import read_temperature_csv
from temperature_report import generate_temperature_report


def _parse_threshold(text: str) -> float:
    """Validate the CLI threshold before any file is opened."""
    try:
        threshold = float(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Der Schwellenwert muss eine endliche Zahl sein."
        ) from error

    if not math.isfinite(threshold):
        raise argparse.ArgumentTypeError(
            "Der Schwellenwert muss eine endliche Zahl sein."
        )
    return threshold


def _parse_model(text: str) -> str:
    """Reject empty model names before processing or creating a log file."""
    if not text.strip():
        raise argparse.ArgumentTypeError("Der Modellname darf nicht leer sein.")
    return text


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, calculate all results, and then print a report.

    With argv=None, argparse reads the process arguments. A supplied list
    contains arguments without the program name. Return 0 on success or 1
    for expected file, format, analysis, model, or logging errors. argparse exits directly
    with 0 for help and 2 for invalid command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description=("Temperaturmessungen aus einer CSV-Datei auswerten; "
                     "optional ausdrücklich einen Online-Modellbericht anfordern."),
        add_help=False,
        allow_abbrev=False,
    )
    # An explicit group and help action keep the help descriptions in German.
    arguments = parser.add_argument_group("Argumente")
    arguments.add_argument("path", metavar="DATEI", help="Pfad zur UTF-8-CSV-Datei.")
    arguments.add_argument(
        "--threshold",
        type=_parse_threshold,
        default=60.0,
        metavar="ZAHL",
        help="Endlicher Schwellenwert in °C (Standard: 60.0); zählt nur Werte darüber.",
    )
    arguments.add_argument(
        "--model-report",
        action="store_true",
        help="Zusätzlich einen Bericht über die OpenAI-API anfordern (benötigt OPENAI_API_KEY).",
    )
    arguments.add_argument(
        "--model",
        type=_parse_model,
        metavar="NAME",
        help="Modell für --model-report (Standard: gpt-4.1-mini); nur mit dieser Option erlaubt.",
    )
    arguments.add_argument(
        "--log-dir",
        metavar="VERZEICHNIS",
        help="Technische Ablaufereignisse in einer neuen JSONL-Datei protokollieren.",
    )
    arguments.add_argument(
        "-h", "--help", action="help", help="Diese Hilfe anzeigen und beenden."
    )

    # Argument errors and help exit here, before files or logs are created.
    args = parser.parse_args(argv)
    if args.model is not None and not args.model_report:
        parser.error("--model ist nur zusammen mit --model-report erlaubt.")

    model_report = None
    try:
        with log_run(args.log_dir) as logger:
            with log_step(logger, "csv_import"):
                records = read_temperature_csv(args.path)
            with log_step(logger, "temperature_analysis"):
                temperatures = [record["temperature_c"] for record in records]
                result = analyze_temperatures(temperatures, threshold=args.threshold)
            if args.model_report:
                model = args.model if args.model is not None else "gpt-4.1-mini"

                def generate_model_text(prompt: str) -> str:
                    """Bind the selected model to the report's one-argument generator."""
                    return generate_text(prompt, model=model)

                with log_step(logger, "model_report"):
                    model_report = generate_temperature_report(
                        result, args.threshold, generate_model_text
                    )
    except RunLoggingError as error:
        print(f"Fehler bei der Protokollierung: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f"Fehler bei der Temperaturauswertung: {error}", file=sys.stderr)
        return 1
    except OpenAITextError as error:
        print(f"Fehler bei der Modellberichterstellung: {error}", file=sys.stderr)
        return 1

    # Calculation, optional model report, final log event, and file close must succeed.
    # Plain string conversion preserves the normal number representation.
    report = "\n".join([
        "Temperaturauswertung",
        f"Messwerte insgesamt: {result['total_count']}",
        f"Gültige Messwerte: {result['valid_count']}",
        f"Fehlende Messwerte: {result['missing_count']}",
        f"Minimum: {result['minimum']} °C",
        f"Maximum: {result['maximum']} °C",
        f"Arithmetischer Mittelwert: {result['mean']} °C",
        f"Schwellenwert: {args.threshold} °C",
        f"Werte strikt oberhalb des Schwellenwerts: {result['exceedance_count']}",
    ])
    if model_report is not None:
        report += "\n\nModellbericht:\n" + model_report
    print(report)
    return 0


# Importing this module defines functions without starting an analysis.
# SystemExit makes main's return value the process exit code.
if __name__ == "__main__":
    raise SystemExit(main())
