"""Provide a terminal interface for CSV import and temperature analysis."""

import argparse
import math
import sys

from temperature_analysis import analyze_temperatures
from temperature_csv import read_temperature_csv


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


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, calculate all results, and then print a report.

    With argv=None, argparse reads the process arguments. A supplied list
    contains arguments without the program name. Return 0 on success or 1
    for expected file, format, or analysis errors. argparse exits directly
    with 0 for help and 2 for invalid command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Temperaturmessungen aus einer CSV-Datei offline auswerten.",
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
        "-h", "--help", action="help", help="Diese Hilfe anzeigen und beenden."
    )

    # argparse validates the threshold here, before read_temperature_csv runs.
    args = parser.parse_args(argv)
    try:
        records = read_temperature_csv(args.path)
        temperatures = [record["temperature_c"] for record in records]
        result = analyze_temperatures(temperatures, threshold=args.threshold)
    except (OSError, ValueError) as error:
        print(f"Fehler bei der Temperaturauswertung: {error}", file=sys.stderr)
        return 1

    # Build the report only after the complete calculation has succeeded.
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
    print(report)
    return 0


# Importing this module defines functions without starting an analysis.
# SystemExit makes main's return value the process exit code.
if __name__ == "__main__":
    raise SystemExit(main())
