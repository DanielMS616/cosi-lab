"""Persist completed analysis and demo runs using the unchanged SQLite schema."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

from openai_text import OpenAITextError, OpenAITextResult
from run_record import (
    AnalysisRun, ApprovalDecision, CompletedRun, ExportReference, ModelCallReference, ReportReference,
)


SCHEMA_PATH = Path(__file__).resolve().parent / "db/schema.sql"
APPLICATION_ID = 1129272137
SCHEMA_VERSION = 1


class SQLiteStorageError(Exception):
    """Expose a storage failure without requiring SQLite imports in orchestration."""


def open_database(path: str | Path) -> sqlite3.Connection:
    """Open an existing database and enable both guards on every connection.

    SQLite connection context managers commit/roll back but do not close the
    connection. Callers must close it, e.g. with contextlib.closing.
    mode=rw prevents an accidental database creation during later reads.
    """
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True)
    try:
        _enable_guards(connection)
    except BaseException:
        connection.close()
        raise
    return connection


def _enable_guards(connection: sqlite3.Connection) -> None:
    """Enable and verify constraints before starting any transaction."""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    for setting in ("foreign_keys", "recursive_triggers"):
        if connection.execute(f"PRAGMA {setting}").fetchone()[0] != 1:
            raise sqlite3.OperationalError(f"Could not enable {setting}.")


def _schema_objects(connection: sqlite3.Connection) -> list[tuple]:
    """Read application DDL, excluding SQLite's internal indexes/statistics."""
    return connection.execute(
        """SELECT type, name, tbl_name, sql FROM sqlite_schema
           WHERE name NOT GLOB 'sqlite_*' ORDER BY type, name"""
    ).fetchall()


def _validate_database(connection: sqlite3.Connection, schema: str) -> None:
    """Reject foreign, unknown or modified schemas before inserting any evidence.

    The reference is built in memory from the unchanged SQL file. Comparing DDL
    includes constraints and triggers, rather than trusting two header numbers.
    This deliberately accepts only our shipped schema, not hand-edited variants.
    """
    if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
        raise SQLiteStorageError("Keine Cosi-Datenbank: fremde Datenbankkennung.")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        raise SQLiteStorageError(f"Unbekannte Cosi-Schemaversion: {version}.")
    with closing(sqlite3.connect(":memory:")) as reference:
        _enable_guards(reference)
        reference.executescript(schema)
        if _schema_objects(connection) != _schema_objects(reference):
            raise SQLiteStorageError("Inkompatibles Cosi-Schema: Tabellen, Indizes oder Trigger weichen ab.")


@contextmanager
def _run_transaction(path: str | Path, *, initialize: bool = False) -> Iterator[sqlite3.Connection]:
    """Validate and bracket one transaction, optionally creating a new database.

    Close before returning to the caller, so an external model request cannot
    accidentally keep this transaction open. Existing files are never migrated.
    Finalization uses initialize=False: a missing database must not be recreated.
    """
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    target = Path(path)
    created = False
    if initialize:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb"):
                pass
            created = True
        except FileExistsError:
            pass

    try:
        with closing(open_database(target)) as connection:
            if created:
                connection.executescript(schema)
            with connection:
                # Hold the write lock while checking compatibility and inserting.
                # BEGIN itself changes no data; validation precedes every INSERT.
                connection.execute("BEGIN IMMEDIATE")
                _validate_database(connection, schema)
                yield connection
    except sqlite3.Error as error:
        raise SQLiteStorageError(f"SQLite-Speicherung fehlgeschlagen: {error}") from error


def _insert_run_input_analysis(
    connection: sqlite3.Connection, run: AnalysisRun, *, model_report: bool = False,
    keep_run_open: bool = False,
) -> str:
    """Insert common evidence, leaving pending model or export runs open."""
    pending = model_report or keep_run_open
    connection.execute(
        """INSERT INTO runs (
            run_id, task_type, execution_mode, settings_json, started_at,
            finished_at, duration_ms, status
        ) VALUES (?, ?, 'fixed', ?, ?, ?, ?, ?)""",
        (run.run_id, "temperature_report" if model_report else "temperature_analysis",
         _json_text({"simulation": False, "threshold": run.threshold}), run.started_at,
         None if pending else run.finished_at, None if pending else run.duration_ms,
         "running" if pending else "succeeded"),
    )
    input_id = _insert_artifact(
        connection, run.run_id, kind="input_file", name=run.input_path.name,
        media_type="text/csv", content=run.input_bytes, file_path=run.input_path,
        created_at=run.started_at,
    )
    return _insert_artifact(
        connection, run.run_id, kind="analysis", name="temperature_analysis",
        media_type="application/json", content=_json_text(run.analysis).encode("utf-8"),
        created_at=run.finished_at, source_id=input_id,
    )


def save_analysis_run(path: str | Path, run: AnalysisRun) -> str:
    """Initialize or append one atomic analysis run, preserving earlier evidence."""
    with _run_transaction(path, initialize=True) as connection:
        _insert_run_input_analysis(connection, run)
    return run.run_id


def prepare_model_run(
    path: str | Path, run: AnalysisRun, *, prompt: str, model: str, started_at: str,
) -> ModelCallReference:
    """Commit the real prompt and start evidence before any model request."""
    call_id = str(uuid4())
    with _run_transaction(path, initialize=True) as connection:
        analysis_id = _insert_run_input_analysis(connection, run, model_report=True)
        connection.execute(
            """INSERT INTO model_calls (
                call_id, run_id, call_index, input_artifact_id, provider, model_requested,
                prompt_text, prompt_sha256, request_json, started_at, status
            ) VALUES (?, ?, 1, ?, 'openai', ?, ?, ?, ?, ?, 'started')""",
            (call_id, run.run_id, analysis_id, model, prompt, _sha256(prompt.encode("utf-8")),
             _json_text({"model": model, "input": prompt, "max_output_tokens": 600, "store": False}),
             started_at),
        )
    return ModelCallReference(run.run_id, call_id, analysis_id)


def _require_pending_call(connection: sqlite3.Connection, call: ModelCallReference) -> None:
    """Only finalize the matching open run/call; never overwrite a completed call."""
    pending = connection.execute(
        """SELECT 1 FROM model_calls m JOIN runs r ON r.run_id = m.run_id
           WHERE m.call_id = ? AND m.run_id = ? AND m.input_artifact_id = ?
             AND m.status = 'started' AND r.status = 'running'""",
        (call.call_id, call.run_id, call.analysis_id),
    ).fetchone()
    if pending is None:
        raise SQLiteStorageError("Kein passender offener Modellaufruf zum Abschließen vorhanden.")


def _finish_run(
    connection: sqlite3.Connection, run_id: str, *, status: str,
    finished_at: str, duration_ms: float, error_code: str | None = None,
) -> None:
    """Finalize the owning run together with its current model/export operation."""
    connection.execute(
        """UPDATE runs SET status = ?, finished_at = ?, duration_ms = ?, error_code = ?
           WHERE run_id = ?""",
        (status, finished_at, duration_ms, error_code, run_id),
    )


def complete_model_run(
    path: str | Path, call: ModelCallReference, *, result: OpenAITextResult,
    report: str, finished_at: str, run_duration_ms: float, keep_run_open: bool = False,
) -> ReportReference:
    """Atomically finalize the call, insert the displayed report and finish the run.

    Persist only metadata delivered by the typed adapter. In particular, a
    successful result does not expose an HTTP status, raw JSON or raw headers.
    With keep_run_open, the model call finishes but the run awaits an export
    decision. A failed commit retains running/started evidence.
    """
    with _run_transaction(path) as connection:
        _require_pending_call(connection, call)
        connection.execute(
            """UPDATE model_calls SET status = 'succeeded', finished_at = ?, duration_ms = ?,
                model_returned = ?, response_id = ?, request_id = ?, response_text = ?,
                input_tokens = ?, output_tokens = ?, total_tokens = ? WHERE call_id = ? AND run_id = ?""",
            (finished_at, result.duration_ms, result.returned_model, result.response_id,
             result.request_id, result.text, result.input_tokens, result.output_tokens,
             result.total_tokens, call.call_id, call.run_id),
        )
        report_ref = _archive_report(
            connection, call.run_id, report=report, created_at=finished_at,
            source_id=call.analysis_id, call_id=call.call_id,
        )
        if not keep_run_open:
            _finish_run(connection, call.run_id, status="succeeded", finished_at=finished_at, duration_ms=run_duration_ms)
    return report_ref


def fail_model_run(
    path: str | Path, call: ModelCallReference, *, error: OpenAITextError,
    finished_at: str, run_duration_ms: float, call_duration_ms: float,
) -> None:
    """Atomically persist safe adapter diagnostics and fail the run without a report.

    No exception messages, credentials or raw server errors enter the database.
    Error duration is measured locally because the adapter returns no result.
    """
    with _run_transaction(path) as connection:
        _require_pending_call(connection, call)
        connection.execute(
            """UPDATE model_calls SET status = 'failed', finished_at = ?, duration_ms = ?,
                error_code = ?, http_status = ? WHERE call_id = ? AND run_id = ?""",
            (finished_at, call_duration_ms, error.error_code, error.http_status, call.call_id, call.run_id),
        )
        _finish_run(connection, call.run_id, status="failed", finished_at=finished_at,
                    duration_ms=run_duration_ms, error_code=error.error_code)


def _archive_report(
    connection: sqlite3.Connection, run_id: str, *, report: str, created_at: str,
    source_id: str, call_id: str | None = None,
) -> ReportReference:
    """Insert exact report bytes and return the identity used by approval guards."""
    content = report.encode("utf-8")
    artifact_id = _insert_artifact(
        connection, run_id, kind="report", name="temperature_report", media_type="text/plain",
        content=content, created_at=created_at, source_id=source_id, call_id=call_id,
    )
    return ReportReference(run_id, artifact_id, _sha256(content), len(content))


def archive_analysis_report(path: str | Path, run: AnalysisRun, report: str) -> ReportReference:
    """Commit input, analysis and the exact report before terminal approval."""
    with _run_transaction(path, initialize=True) as connection:
        analysis_id = _insert_run_input_analysis(connection, run, keep_run_open=True)
        report_ref = _archive_report(
            connection, run.run_id, report=report, created_at=run.finished_at, source_id=analysis_id,
        )
    return report_ref


def record_export_decision(
    path: str | Path, report: ReportReference, target: Path, decision: ApprovalDecision, *,
    decided_at: str, run_duration_ms: float,
) -> ExportReference | None:
    """Commit approval and, only for explicit yes, the export start together.

    A decline finalizes the run successfully without creating an export. The
    schema enforces the exact report/hash/target binding and explicit_yes reason.
    All connections/transactions are closed before returning for file I/O.
    """
    approval_id = str(uuid4())
    export_id = str(uuid4()) if decision.approved else None
    with _run_transaction(path) as connection:
        archived = connection.execute(
            """SELECT 1 FROM artifacts a JOIN runs r ON r.run_id = a.run_id
               WHERE a.artifact_id = ? AND a.run_id = ? AND a.kind = 'report'
                 AND a.content_sha256 = ? AND a.byte_count = ? AND r.status = 'running'""",
            (report.artifact_id, report.run_id, report.content_sha256, report.byte_count),
        ).fetchone()
        if archived is None:
            raise SQLiteStorageError("Kein passender archivierter Bericht in einem offenen Lauf vorhanden.")
        connection.execute(
            """INSERT INTO approvals (
                approval_id, run_id, artifact_id, action, target_path, content_sha256,
                decision, reason_code, actor, decided_at
            ) VALUES (?, ?, ?, 'export_report', ?, ?, ?, ?, 'terminal_user', ?)""",
            (approval_id, report.run_id, report.artifact_id, str(target), report.content_sha256,
             "approved" if decision.approved else "declined", decision.reason_code, decided_at),
        )
        if decision.approved:
            connection.execute(
                """INSERT INTO exports (
                    export_id, run_id, artifact_id, approval_id, target_path, content_sha256,
                    started_at, status, file_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'started', 'unknown')""",
                (export_id, report.run_id, report.artifact_id, approval_id, str(target),
                 report.content_sha256, decided_at),
            )
        else:
            _finish_run(connection, report.run_id, status="succeeded", finished_at=decided_at,
                        duration_ms=run_duration_ms)
    if export_id is None:
        return None
    return ExportReference(report.run_id, export_id, report.artifact_id, target, report.byte_count)


def finish_export(
    path: str | Path, export: ExportReference, *, finished_at: str, duration_ms: float,
    run_duration_ms: float, error_code: str | None = None,
) -> None:
    """Atomically confirm file completion or record failure, then finalize the run.

    A file error does not establish absent/partial/complete file state, so retain
    unknown and no byte count. On success write_report has written and closed the
    exact archived bytes. A database failure rolls back this confirmation only.
    """
    status = "succeeded" if error_code is None else "failed"
    with _run_transaction(path) as connection:
        pending = connection.execute(
            """SELECT 1 FROM exports e JOIN runs r ON r.run_id = e.run_id
               WHERE e.export_id = ? AND e.run_id = ? AND e.artifact_id = ? AND e.target_path = ?
                 AND e.status = 'started' AND r.status = 'running'""",
            (export.export_id, export.run_id, export.artifact_id, str(export.target_path)),
        ).fetchone()
        if pending is None:
            raise SQLiteStorageError("Kein passender offener Export zum Abschließen vorhanden.")
        connection.execute(
            """UPDATE exports SET status = ?, finished_at = ?, duration_ms = ?,
                file_state = ?, written_bytes = ?, error_code = ? WHERE export_id = ? AND run_id = ?""",
            (status, finished_at, duration_ms, "complete" if error_code is None else "unknown",
             export.byte_count if error_code is None else None, error_code, export.export_id, export.run_id),
        )
        _finish_run(connection, export.run_id, status=status, finished_at=finished_at,
                    duration_ms=run_duration_ms, error_code=error_code)


def _json_text(value: object) -> str:
    """Serialize structured evidence without rounding or non-JSON numbers."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _sha256(content: bytes) -> str:
    """Fingerprint exactly the bytes represented by an artifact or prompt."""
    return hashlib.sha256(content).hexdigest()


def _insert_artifact(
    connection: sqlite3.Connection, run_id: str, *, kind: str, name: str,
    media_type: str, content: bytes, created_at: str,
    file_path: Path | None = None, source_id: str | None = None,
    call_id: str | None = None,
) -> str:
    """Insert one immutable artifact, retaining file inputs as references."""
    artifact_id = str(uuid4())
    content_text = None if file_path is not None else content.decode("utf-8")
    connection.execute(
        """INSERT INTO artifacts (
            artifact_id, run_id, kind, logical_name, version, source_artifact_id,
            model_call_id, media_type, content_text, file_path, content_sha256,
            byte_count, created_at
        ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (artifact_id, run_id, kind, name, source_id, call_id, media_type,
         content_text, str(file_path) if file_path is not None else None,
         _sha256(content), len(content), created_at),
    )
    return artifact_id


def save_demo_run(path: str | Path, run: CompletedRun) -> str:
    """Save a simulation; preserve filesystem errors and translate SQLite errors."""
    try:
        return _write_demo_run(path, run)
    except sqlite3.Error as error:
        raise SQLiteStorageError(f"SQLite-Speicherung fehlgeschlagen: {error}") from error


def _write_demo_run(path: str | Path, run: CompletedRun) -> str:
    """Create a new database and atomically insert one completed simulation.

    Exclusive file creation rejects files, directories and even dangling links
    before SQLite opens the target. Schema creation is separate from the data
    transaction: on failure an empty/initialized database may remain and must be
    inspected or removed explicitly before retrying. Existing paths are untouched.
    No approval or export is recorded because no report file is exported.
    """
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb"):
        pass

    run_id = str(uuid4())
    call_id = str(uuid4())
    result = run.model_result
    with closing(open_database(target)) as connection:
        connection.executescript(schema)
        # Insert in dependency order; a later failure rolls back all evidence.
        with connection:
            connection.execute(
                """INSERT INTO runs (
                    run_id, task_type, execution_mode, settings_json, started_at,
                    finished_at, duration_ms, status
                ) VALUES (?, 'temperature_report_demo', 'fixed', ?, ?, ?, ?, 'succeeded')""",
                (run_id, _json_text({"simulation": True, "threshold": run.threshold}),
                 run.started_at, run.finished_at, run.duration_ms),
            )
            input_id = _insert_artifact(
                connection, run_id, kind="input_file", name=run.input_path.name,
                media_type="text/csv", content=run.input_bytes,
                created_at=run.started_at, file_path=run.input_path,
            )
            analysis_id = _insert_artifact(
                connection, run_id, kind="analysis", name="temperature_analysis",
                media_type="application/json", content=_json_text(run.analysis).encode("utf-8"),
                created_at=run.model_started_at, source_id=input_id,
            )
            connection.execute(
                """INSERT INTO model_calls (
                    call_id, run_id, call_index, input_artifact_id, provider,
                    model_requested, model_returned, prompt_text, prompt_sha256,
                    request_json, started_at, finished_at, duration_ms, status,
                    response_id, request_id, response_text,
                    input_tokens, output_tokens, total_tokens
                ) VALUES (?, ?, 1, ?, 'simulation', ?, ?, ?, ?, ?, ?, ?, ?,
                          'succeeded', ?, ?, ?, ?, ?, ?)""",
                (call_id, run_id, analysis_id, result.requested_model, result.returned_model,
                 run.prompt, _sha256(run.prompt.encode("utf-8")),
                 _json_text({"simulation": True, "model": result.requested_model,
                             "input": run.prompt}),
                 run.model_started_at, run.model_finished_at, result.duration_ms,
                 result.response_id, result.request_id, result.text,
                 result.input_tokens, result.output_tokens, result.total_tokens),
            )
            _insert_artifact(
                connection, run_id, kind="report", name="temperature_report",
                media_type="text/plain", content=run.report.encode("utf-8"),
                created_at=run.finished_at, source_id=analysis_id, call_id=call_id,
            )
    return run_id
