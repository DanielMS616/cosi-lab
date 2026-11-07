"""Provide temperature analysis with an explicitly requested optional model report."""

import argparse
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from openai_text import OpenAITextError, OpenAITextResult, generate_text, generate_text_result
from report_storage import new_report_path, write_report
from run_logging import RunLoggingError, log_run, log_step
from run_record import AnalysisRun, ApprovalDecision, ExportReference, ModelCallReference, ReportReference
from sqlite_storage import (
    SQLiteStorageError, archive_analysis_report, complete_model_run, fail_model_run,
    finish_export, prepare_model_run, record_export_decision, save_analysis_run,
)
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


def _utc_now() -> str:
    """Return the schema's UTC timestamp format with six fractional digits."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _format_report(
    result: dict[str, int | float], threshold: float, model_report: str | None
) -> str:
    """Build one complete text, including its final newline, for display and saving."""
    # Plain string conversion preserves the normal number representation.
    report = "\n".join([
        "Temperaturauswertung",
        f"Messwerte insgesamt: {result['total_count']}",
        f"Gültige Messwerte: {result['valid_count']}",
        f"Fehlende Messwerte: {result['missing_count']}",
        f"Minimum: {result['minimum']} °C",
        f"Maximum: {result['maximum']} °C",
        f"Arithmetischer Mittelwert: {result['mean']} °C",
        f"Schwellenwert: {threshold} °C",
        f"Werte strikt oberhalb des Schwellenwerts: {result['exceedance_count']}",
    ])
    if model_report is not None:
        report += "\n\nModellbericht:\n" + model_report
    return report + "\n"


def _request_save_decision() -> ApprovalDecision:
    """Normalize terminal input and distinguish denial, EOF and interruption."""
    try:
        answer = input("Diesen Bericht am angezeigten Ziel speichern? Nur 'ja' erlaubt Speichern: ")
    except EOFError:
        print("\nEingabe beendet; keine Freigabe.")
        return ApprovalDecision(False, "eof")
    except KeyboardInterrupt:
        print("\nEingabe beendet; keine Freigabe.")
        return ApprovalDecision(False, "interrupted")
    approved = answer.strip().casefold() == "ja"
    return ApprovalDecision(approved, "explicit_yes" if approved else "not_approved")


def _request_save_approval() -> bool:
    """Keep the existing boolean interface for exports without a database."""
    return _request_save_decision().approved


def _generate_database_report(
    database_path: str, run: AnalysisRun, model: str, run_started_counter: float,
    *, keep_run_open: bool = False,
) -> tuple[str, ReportReference]:
    """Persist start evidence, request once and atomically record the outcome.

    The report function supplies the actual prompt to our generator. Preparation
    must return after commit/close before the adapter is called. No retry follows
    a model failure or a failed final save. Unexpected interruption leaves the
    committed start evidence open rather than claiming a confirmed outcome.
    """
    call: ModelCallReference | None = None
    response: OpenAITextResult | None = None

    def generate_recorded_text(prompt: str) -> str:
        """Adapt the typed result and preserve failure diagnostics before re-raising."""
        # nonlocal updates the surrounding function's variables, so it can
        # finalize the same call/result after the report function has returned.
        nonlocal call, response
        call = prepare_model_run(database_path, run, prompt=prompt, model=model, started_at=_utc_now())
        call_started_counter = time.perf_counter()
        try:
            response = generate_text_result(prompt, model=model)
        except OpenAITextError as error:
            fail_model_run(
                database_path, call, error=error, finished_at=_utc_now(),
                run_duration_ms=(time.perf_counter() - run_started_counter) * 1000,
                call_duration_ms=(time.perf_counter() - call_started_counter) * 1000,
            )
            raise
        return response.text

    model_report = generate_temperature_report(run.analysis, run.threshold, generate_recorded_text)
    if call is None or response is None:
        raise ValueError("Die Berichtsfunktion hat keinen Modellaufruf ausgeführt.")
    report_ref = complete_model_run(
        database_path, call, result=response,
        report=_format_report(run.analysis, run.threshold, model_report),
        finished_at=_utc_now(), run_duration_ms=(time.perf_counter() - run_started_counter) * 1000,
        keep_run_open=keep_run_open,
    )
    return model_report, report_ref


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, calculate all results, and then print a report.

    With argv=None, argparse reads the process arguments. A supplied list
    contains arguments without the program name. Return 0 on success or 1
    for expected file, format, analysis, model, storage, or logging errors. argparse exits directly
    with 0 for help and 2 for invalid command-line arguments.
    Saving requires a preview and explicit approval. Declining or interrupting
    approval returns 0 without saving, unless logging fails. A preview is not
    a success report; saving and final logging must succeed before confirmation.
    --database archives reports before approval, then records the decision and
    export lifecycle. Without it, no database is opened or initialized.
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
        "--save-report",
        action="store_true",
        help="Bericht als Vorschau zeigen und erst nach 'ja' unter reports/<UUID>.txt speichern.",
    )
    arguments.add_argument(
        "--database",
        metavar="PATH",
        help="CSV-Verweis und Analyse in einer neuen oder kompatiblen Cosi-Datenbank speichern; "
             "mit --model-report auch Modellaufruf, mit --save-report auch Freigabe und Datei-Export.",
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
    target_path = None
    save_attempted = False
    saved = False
    database_saved = False
    # This flag tracks the current operation, so file errors and database errors
    # keep distinct diagnostics even after the report has already been archived.
    database_attempted = False
    report_ref: ReportReference | None = None
    export_ref: ExportReference | None = None
    try:
        with log_run(args.log_dir) as logger:
            if args.database is not None:
                database_started_at = _utc_now()
                database_started_counter = time.perf_counter()
            with log_step(logger, "csv_import"):
                if args.database is not None:
                    input_path = Path(args.path).resolve()
                    input_bytes = input_path.read_bytes()
                records = read_temperature_csv(args.path)
                if args.database is not None and input_path.read_bytes() != input_bytes:
                    raise ValueError("Die CSV-Datei wurde während des Imports geändert.")
            with log_step(logger, "temperature_analysis"):
                temperatures = [record["temperature_c"] for record in records]
                result = analyze_temperatures(temperatures, threshold=args.threshold)
            if args.database is not None:
                # Reuse the log identity when both storage formats are requested.
                run_id = logger.run_id if logger is not None else str(uuid4())
                run = AnalysisRun(
                    run_id=run_id, input_path=input_path, input_bytes=input_bytes,
                    analysis=result, threshold=args.threshold, started_at=database_started_at,
                    finished_at=_utc_now(),
                    duration_ms=(time.perf_counter() - database_started_counter) * 1000,
                )
            if args.model_report:
                model = args.model if args.model is not None else "gpt-4.1-mini"

                def generate_model_text(prompt: str) -> str:
                    """Bind the selected model to the report's one-argument generator."""
                    return generate_text(prompt, model=model)

                with log_step(logger, "model_report"):
                    if args.database is not None:
                        database_attempted = True
                        model_report, report_ref = _generate_database_report(
                            args.database, run, model, database_started_counter,
                            keep_run_open=args.save_report,
                        )
                        database_saved = True
                        database_attempted = False
                    else:
                        model_report = generate_temperature_report(
                            result, args.threshold, generate_model_text
                        )
            report = _format_report(result, args.threshold, model_report)
            if args.database is not None and not args.model_report:
                with log_step(logger, "database_save"):
                    database_attempted = True
                    if args.save_report:
                        report_ref = archive_analysis_report(args.database, run, report)
                    else:
                        save_analysis_run(args.database, run)
                    database_saved = True
                    database_attempted = False
            if args.save_report:
                # The program chooses the destination; model text never controls it.
                target_path = new_report_path()
                if args.database is not None:
                    target_path = target_path.resolve()
                    print(f"Vorschau — noch nicht als Datei gespeichert. Zielpfad: {target_path}")
                else:
                    print(f"Vorschau — noch nicht gespeichert. Zielpfad: {target_path}")
                print("--- Bericht beginnt ---")
                print(report, end="")
                print("--- Bericht endet ---")
                if args.database is not None:
                    if report_ref is None:
                        raise SQLiteStorageError("Der Bericht wurde vor der Freigabe nicht archiviert.")
                    decision = _request_save_decision()
                    approved = decision.approved
                    database_attempted = True
                    export_ref = record_export_decision(
                        args.database, report_ref, target_path, decision, decided_at=_utc_now(),
                        run_duration_ms=(time.perf_counter() - database_started_counter) * 1000,
                    )
                    database_attempted = False
                    if approved and export_ref is None:
                        raise SQLiteStorageError("Der Exportstart wurde nicht bestätigt.")
                else:
                    approved = _request_save_approval()
                if logger is not None:
                    event = "save_approved" if approved else "save_declined"
                    logger.write_event(event, "report_save", "success")
                if approved:
                    with log_step(logger, "report_save"):
                        export_started_counter = time.perf_counter() if args.database is not None else None
                        save_attempted = True
                        try:
                            write_report(target_path, report)
                        except (OSError, ValueError) as error:
                            if export_ref is not None:
                                database_attempted = True
                                finish_export(
                                    args.database, export_ref, finished_at=_utc_now(),
                                    duration_ms=(time.perf_counter() - export_started_counter) * 1000,
                                    run_duration_ms=(time.perf_counter() - database_started_counter) * 1000,
                                    error_code="file_exists" if isinstance(error, FileExistsError) else "file_error",
                                )
                                database_attempted = False
                            raise
                        # Set this before step_finished: even that log write can fail.
                        saved = True
                        if export_ref is not None:
                            database_attempted = True
                            finish_export(
                                args.database, export_ref, finished_at=_utc_now(),
                                duration_ms=(time.perf_counter() - export_started_counter) * 1000,
                                run_duration_ms=(time.perf_counter() - database_started_counter) * 1000,
                            )
                            database_attempted = False
    except RunLoggingError as error:
        print(f"Fehler bei der Protokollierung: {error}", file=sys.stderr)
        if database_saved:
            print("Der Lauf wurde bereits in der Datenbank gespeichert; "
                  "Protokollabschluss nicht erfolgreich.", file=sys.stderr)
        if saved:
            print(f"Bericht wurde bereits vollständig geschrieben und geschlossen: {target_path}. "
                  "Protokollabschluss nicht erfolgreich.", file=sys.stderr)
        elif save_attempted:
            print("Schreibabschluss nicht bestätigt; am Ziel kann eine unvollständige Datei vorliegen.",
                  file=sys.stderr)
        elif args.save_report:
            print("Bericht wurde nicht gespeichert.", file=sys.stderr)
        return 1
    except SQLiteStorageError as error:
        print(f"Fehler beim Speichern in der Datenbank: {error}", file=sys.stderr)
        if saved:
            print(f"Die Datei wurde bereits vollständig geschrieben und geschlossen: {target_path}. "
                  "Nur die Bestätigung in der Datenbank fehlt. Der Export wird nicht wiederholt.", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        if database_attempted:
            print(f"Fehler beim Speichern in der Datenbank: {error}", file=sys.stderr)
            if saved:
                print(f"Die Datei wurde bereits vollständig geschrieben und geschlossen: {target_path}. "
                      "Nur die Bestätigung in der Datenbank fehlt. Der Export wird nicht wiederholt.", file=sys.stderr)
        elif save_attempted:
            print(f"Fehler beim Speichern des Berichts: {error}", file=sys.stderr)
            print("Schreibabschluss nicht bestätigt; eine vorhandene Zieldatei wurde nicht "
                  "überschrieben, eine neu angelegte Datei kann unvollständig sein.", file=sys.stderr)
        else:
            print(f"Fehler bei der Temperaturauswertung: {error}", file=sys.stderr)
        return 1
    except OpenAITextError as error:
        print(f"Fehler bei der Modellberichterstellung: {error}", file=sys.stderr)
        return 1

    # Only confirm success after the final log event and log-file close.
    if args.save_report:
        if saved:
            print(f"Bericht gespeichert: {target_path}")
        else:
            print("Nicht gespeichert: keine Freigabe.")
        if args.log_dir is not None:
            print("Protokollierung erfolgreich abgeschlossen.")
    else:
        print(report, end="")
    return 0


# Importing this module defines functions without starting an analysis.
# SystemExit makes main's return value the process exit code.
if __name__ == "__main__":
    raise SystemExit(main())
