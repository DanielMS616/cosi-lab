"""Show a read-only, one-line metadata overview of stored Cosi runs."""

import argparse
import json
import sys
from pathlib import Path

from run_record import RunSummary
from sqlite_storage import SQLiteStorageError, list_runs


def _parse_limit(text: str) -> int:
    """Reject invalid limits before opening any database."""
    try:
        limit = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("--limit muss eine positive Ganzzahl sein.") from None
    if not 1 <= limit <= 2**63 - 1:
        raise argparse.ArgumentTypeError("--limit muss eine positive Ganzzahl im SQLite-Zahlenbereich sein.")
    return limit


def _single_line(value: str) -> str:
    """Escape control characters so metadata cannot create extra output lines."""
    encoded = json.dumps(value, ensure_ascii=True)
    # Retain JSON's escaping, but remove the surrounding quotation marks.
    return encoded[1:-1]


def _format_run(run: RunSummary) -> str:
    """Format only overview fields and identify unconfirmed lifecycle states."""
    parts = [
        _single_line(run.run_id), _single_line(run.started_at),
        _single_line(run.task_type), f"status={run.status}",
    ]
    optional_fields = (
        ("model_status", run.model_status), ("model_returned", run.model_returned),
        ("run_error_code", run.run_error_code), ("model_error_code", run.model_error_code),
        ("http_status", run.http_status), ("approval", run.approval_status),
        ("export", run.export_status), ("export_error_code", run.export_error_code),
    )
    for label, value in optional_fields:
        if value is not None:
            parts.append(f"{label}={_single_line(str(value))}")
    pending = []
    if run.status == "running":
        pending.append("Lauf")
    if run.model_status == "started":
        pending.append("Modellaufruf")
    if run.export_status == "started":
        pending.append("Export")
    if pending:
        parts.append("kein Abschluss gespeichert: " + ", ".join(pending))
    return " | ".join(parts)


def main(argv: list[str] | None = None) -> int:
    """Read the newest stored runs; report errors without creating database files."""
    parser = argparse.ArgumentParser(description="Gespeicherte Cosi-Läufe schreibgeschützt anzeigen.", allow_abbrev=False)
    parser.add_argument("--database", required=True, type=Path, metavar="PATH", help="Vorhandene Cosi-Datenbank.")
    parser.add_argument("--limit", type=_parse_limit, default=20, metavar="ANZAHL", help="Höchstens so viele Läufe anzeigen (Standard: 20).")
    args = parser.parse_args(argv)
    try:
        runs = list_runs(args.database, limit=args.limit)
    except (SQLiteStorageError, OSError, ValueError) as error:
        print(f"Fehler beim Lesen der Laufübersicht: {error}", file=sys.stderr)
        return 1
    for run in runs:
        print(_format_run(run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
