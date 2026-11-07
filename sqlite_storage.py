"""Persist completed analysis and demo runs using the unchanged SQLite schema."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from run_record import AnalysisRun, CompletedRun


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


def save_analysis_run(path: str | Path, run: AnalysisRun) -> str:
    """Initialize a new database or append one atomic run to a compatible one.

    Existing databases are never initialized or migrated. A failed insertion or
    commit rolls back this run, preserving earlier runs. A failed new database
    may retain its empty schema, just like the standalone demo.
    """
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb"):
            pass
        created = True
    except FileExistsError:
        created = False

    try:
        with closing(open_database(target)) as connection:
            if created:
                connection.executescript(schema)
            with connection:
                # Hold the write lock while checking compatibility and inserting.
                # BEGIN itself changes no data; validation precedes every INSERT.
                connection.execute("BEGIN IMMEDIATE")
                _validate_database(connection, schema)
                connection.execute(
                    """INSERT INTO runs (
                        run_id, task_type, execution_mode, settings_json, started_at,
                        finished_at, duration_ms, status
                    ) VALUES (?, 'temperature_analysis', 'fixed', ?, ?, ?, ?, 'succeeded')""",
                    (run.run_id, _json_text({"simulation": False, "threshold": run.threshold}),
                     run.started_at, run.finished_at, run.duration_ms),
                )
                input_id = _insert_artifact(
                    connection, run.run_id, kind="input_file", name=run.input_path.name,
                    media_type="text/csv", content=run.input_bytes, file_path=run.input_path,
                    created_at=run.started_at,
                )
                _insert_artifact(
                    connection, run.run_id, kind="analysis", name="temperature_analysis",
                    media_type="application/json", content=_json_text(run.analysis).encode("utf-8"),
                    created_at=run.finished_at, source_id=input_id,
                )
    except sqlite3.Error as error:
        raise SQLiteStorageError(f"SQLite-Speicherung fehlgeschlagen: {error}") from error
    return run.run_id


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
