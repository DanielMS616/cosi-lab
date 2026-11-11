import sqlite3
import tempfile
import unittest
from pathlib import Path

from model_storage import initialize_database, load_model_run, save_model_run


class ModelStorageTests(unittest.TestCase):
    # Speichert einen bekannten Beispielbericht und danach einen zweiten Lauf.
    # Anschließend liest der Test gezielt die ID des ersten Laufs.
    # Der zweite Eintrag ist wichtig: Würde die Funktion versehentlich immer den neuesten Lauf zurückgeben,
    # würde der Test fehlschlagen. Verglichen werden der vollständige Prompt, die Antwort und alle Metadaten.
    # Dabei wird auch geprüft, dass eine fehlende Anbieterzeit als Python-`None` zurückkommt,
    # also dem NULL in SQLite entspricht.
    def test_reads_the_selected_run_with_its_saved_values(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "model_runs.sqlite3"
            initialize_database(database_path)

            run_id = save_model_run(
                database_path=database_path,
                model="gemini-demo",
                csv_path="examples/temperature_sample.csv",
                threshold=60,
                prompt="Fasse die Kennzahlen zusammen.\nVier Messwerte.",
                response_text="Ein Messwert liegt über 60 °C.",
                duration_ms=None,
                input_tokens=23,
                output_tokens=11,
                requested_at_utc="2026-11-11T10:00:00.000+00:00",
                client_duration_ms=3703,
            )
            # Der jüngste Lauf ist ein anderer, damit die Suche nach ID geprüft wird.
            save_model_run(database_path, "gpt-demo", "andere.csv", 40, "Prompt", "Antwort")

            self.assertEqual(
                load_model_run(database_path, run_id),
                {
                    "id": run_id,
                    "model": "gemini-demo",
                    "csv_path": "examples/temperature_sample.csv",
                    "threshold": 60,
                    "prompt": "Fasse die Kennzahlen zusammen.\nVier Messwerte.",
                    "response_text": "Ein Messwert liegt über 60 °C.",
                    "duration_ms": None,
                    "input_tokens": 23,
                    "output_tokens": 11,
                    "requested_at_utc": "2026-11-11T10:00:00.000+00:00",
                    "client_duration_ms": 3703,
                },
            )

    # Fragt eine ID ab, die es nicht gibt. Die Funktion soll None zurückgeben.
    # So kann die Terminalansicht verständlich melden, dass kein Lauf gefunden wurde.
    def test_unknown_run_returns_none(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "model_runs.sqlite3"
            initialize_database(database_path)
            self.assertIsNone(load_model_run(database_path, 999))

    # versucht, eine nicht vorhandene Datenbank zu lesen.
    # Der Test erwartet einen SQLite-Fehler und prüft zusätzlich, dass keine Datei entstanden ist.
    # So führt ein Tippfehler im Pfad nicht zu einer neuen, leeren Datenbank.
    def test_read_does_not_create_a_missing_database(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "fehlt.sqlite3"
            with self.assertRaises(sqlite3.OperationalError):
                load_model_run(database_path, 1)
            self.assertFalse(database_path.exists())
