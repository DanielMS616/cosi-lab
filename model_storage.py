import sqlite3
from pathlib import Path


def initialize_database(database_path):
    """Erstellt die SQLite-Datenbank und die Tabelle model_runs."""

    # Path ermöglicht eine einheitliche Arbeit mit Dateipfaden.
    database_path = Path(database_path)

    # Falls beispielsweise data/model_runs.sqlite3 angegeben wurde,
    # wird der Ordner data bei Bedarf angelegt.
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # Verbindung zur Datenbank öffnen.
    connection = sqlite3.connect(database_path)

    try:
        # Die Tabelle wird nur erstellt, wenn sie noch nicht existiert.
        # SQLite vergibt den Primärschlüssel id automatisch.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS model_runs (
                id INTEGER PRIMARY KEY,
                model TEXT NOT NULL,
                csv_path TEXT NOT NULL,
                threshold INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                response_text TEXT NOT NULL,
                duration_ms INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                requested_at_utc TEXT,
                client_duration_ms INTEGER
            )
            """
        )

        # PRAGMA table_info liest die vorhandenen Spalten. CREATE TABLE IF NOT EXISTS
        # verändert eine bereits vorhandene Tabelle nicht; deshalb braucht sie einmalig
        # das ALTER TABLE. Alte Einträge bleiben erhalten und bekommen dort NULL.
        columns = {
            column[1] for column in connection.execute("PRAGMA table_info(model_runs)")
        }
        if "requested_at_utc" not in columns:
            connection.execute("ALTER TABLE model_runs ADD COLUMN requested_at_utc TEXT")

        if "client_duration_ms" not in columns:
            connection.execute("ALTER TABLE model_runs ADD COLUMN client_duration_ms INTEGER")

        # Änderungen dauerhaft in die Datenbank schreiben.
        connection.commit()
    finally:
        # Die Verbindung wird auch dann geschlossen, wenn ein Fehler auftritt.
        connection.close()


def save_model_run(
    database_path,
    model,
    csv_path,
    threshold,
    prompt,
    response_text,
    duration_ms=None,
    input_tokens=None,
    output_tokens=None,
    requested_at_utc=None,
    client_duration_ms=None,
):
    """Speichert einen erfolgreichen Modelllauf und gibt seine ID zurück."""

    connection = sqlite3.connect(database_path)

    try:
        cursor = connection.execute(
            """
            INSERT INTO model_runs (
                model,
                csv_path,
                threshold,
                prompt,
                response_text,
                duration_ms,
                input_tokens,
                output_tokens,
                requested_at_utc,
                client_duration_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model,
                str(csv_path),
                threshold,
                prompt,
                response_text,
                duration_ms,
                input_tokens,
                output_tokens,
                requested_at_utc,
                client_duration_ms,
            ),
        )

        connection.commit()

        # lastrowid enthält die automatisch vergebene ID des neuen Datensatzes.
        return cursor.lastrowid
    finally:
        connection.close()