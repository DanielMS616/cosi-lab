"""Speichert RAG-Modellläufe in der lokalen SQLite-Datei."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path


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
