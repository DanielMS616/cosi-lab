"""Speichert und liest RAG-Modellläufe in der lokalen SQLite-Datei."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path


RUN_DATABASE = Path(__file__).resolve().parent / "data" / "model_runs.sqlite3"


def save_rag_run(database_path, run, sources):
    """Speichert Prompt, Antwort, Quellen und Messwerte und gibt die Lauf-ID zurück."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Speichere die tatsächlichen Ausschnitte in ihrer Reihenfolge. Ein
    # späterer Neuimport nach PostgreSQL verändert diese Kopie nicht.
    values = {**run, "sources_json": json.dumps(sources, ensure_ascii=False)}

    # Der Verbindungsblock schreibt bei Erfolg; closing schließt die Datei.
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS rag_runs (
                id INTEGER PRIMARY KEY,
                requested_at_utc TEXT NOT NULL,
                question TEXT NOT NULL,
                top_k INTEGER,
                retrieval_model TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                max_output_tokens INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                response_text TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                e5_load_ms INTEGER NOT NULL,
                retrieval_ms INTEGER NOT NULL,
                client_duration_ms INTEGER NOT NULL,
                provider_duration_ms INTEGER,
                api_status TEXT,
                incomplete_reason TEXT
            )
        """)
        # Die Platzhalternamen passen zu den Schlüsseln im Dictionary values.
        cursor = db.execute("""
            INSERT INTO rag_runs (
                requested_at_utc, question, top_k, retrieval_model, provider,
                model, max_output_tokens, prompt, sources_json, response_text,
                input_tokens, output_tokens, e5_load_ms, retrieval_ms,
                client_duration_ms, provider_duration_ms, api_status, incomplete_reason
            ) VALUES (
                :requested_at_utc, :question, :top_k, :retrieval_model, :provider,
                :model, :max_output_tokens, :prompt, :sources_json, :response_text,
                :input_tokens, :output_tokens, :e5_load_ms, :retrieval_ms,
                :client_duration_ms, :provider_duration_ms, :api_status, :incomplete_reason
            )
        """, values)
        lauf_id = cursor.lastrowid

    return lauf_id


def _oeffne_nur_zum_lesen(database_path):
    """Öffnet SQLite schreibgeschützt und liefert Zeilen mit Spaltennamen."""
    # mode=ro verhindert Änderungen und legt keine fehlende Datei an.
    database_uri = Path(database_path).resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(database_uri, uri=True)
    db.row_factory = sqlite3.Row
    return db


def _rag_tabelle_vorhanden(db):
    # Die gemeinsame Datei kann zunächst nur Temperaturläufe enthalten.
    eintrag = db.execute("""
        SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'rag_runs'
    """).fetchone()
    return eintrag is not None


def load_rag_run(database_path, run_id):
    """Liest einen gespeicherten Lauf schreibgeschützt oder gibt None zurück."""
    with closing(_oeffne_nur_zum_lesen(database_path)) as db:
        if not _rag_tabelle_vorhanden(db):
            return None

        row = db.execute("SELECT * FROM rag_runs WHERE id = ?", (run_id,)).fetchone()

    if row is None:
        return None

    lauf = dict(row)
    # SQLite speichert die Quellen als JSON-Text; die Ansicht braucht die Liste.
    lauf["sources"] = json.loads(lauf.pop("sources_json"))
    return lauf


def list_rag_runs(database_path, limit):
    """Liest die zuletzt gespeicherten RAG-Läufe als kurze Übersicht."""
    if not Path(database_path).exists():
        return []

    with closing(_oeffne_nur_zum_lesen(database_path)) as db:
        if not _rag_tabelle_vorhanden(db):
            return []

        # Je höher die ID, desto später wurde der Lauf gespeichert.
        # Prompt, Antwort und Fundstellen bleiben dem Detailabruf vorbehalten.
        zeilen = db.execute("""
            SELECT id, question, provider, model, requested_at_utc
            FROM rag_runs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(zeile) for zeile in zeilen]
