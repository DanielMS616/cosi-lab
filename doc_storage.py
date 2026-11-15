import json
import sqlite3

from pathlib import Path


def initialize_doc_database(database_path):
    """Legt die Tabelle für Dokufragen an, falls sie noch fehlt."""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    try:
        # Die Tabelle für Temperaturberichte bleibt bestehen.
        # Bereits gespeicherte Dokuläufe bleiben bei erneutem Aufruf erhalten.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_runs (
                id INTEGER PRIMARY KEY,
                model TEXT NOT NULL,
                requested_at_utc TEXT NOT NULL,
                question TEXT NOT NULL,
                prompt TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                response_text TEXT NOT NULL,
                citations_json TEXT NOT NULL,
                api_status TEXT,
                incomplete_reason TEXT
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def save_doc_run(
    database_path,
    *,
    model,
    requested_at_utc,
    question,
    prompt,
    hits,
    response_text,
    citations,
    api_status=None,
    incomplete_reason=None,
):
    """Speichert einen Dokulauf in der vorbereiteten Datenbank und gibt seine ID zurück."""

    # Halte nur fest, was dem Modell als Quelle vorlag. Die Suchtreffer
    # behalten ihre Reihenfolge; interne Suchwörter speichern wir hier nicht.
    sources = []
    for hit in hits:
        sources.append({
            "path": str(hit["path"]),
            "start_line": hit["start_line"],
            "end_line": hit["end_line"],
            "text": hit["text"],
        })

    # SQLite speichert JSON als Text. Umlaute bleiben dabei lesbar.
    sources_json = json.dumps(sources, ensure_ascii=False)
    citations_json = json.dumps(citations, ensure_ascii=False)

    connection = sqlite3.connect(database_path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO doc_runs (
                model, requested_at_utc, question, prompt, sources_json,
                response_text, citations_json, api_status, incomplete_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model, requested_at_utc, question, prompt, sources_json,
                response_text, citations_json, api_status, incomplete_reason,
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()