import tempfile
import unittest
from pathlib import Path

from doc_storage import initialize_doc_database, list_doc_runs, save_doc_run


class DocStorageTests(unittest.TestCase):
    def test_list_returns_the_last_two_saved_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "runs.sqlite3"
            initialize_doc_database(database_path)

            # Die Aufrufzeiten laufen rückwärts. So fällt im Test auf,
            # wenn versehentlich nach der Uhrzeit statt nach ID sortiert wird.
            cases = [
                ("Erste Frage", "2026-11-15T12:00:00+00:00"),
                ("Zweite Frage", "2026-11-15T11:00:00+00:00"),
                ("Dritte Frage", "2026-11-15T10:00:00+00:00"),
            ]

            ids = []
            for question, requested_at in cases:
                run_id = save_doc_run(
                    database_path,
                    model="gpt-test",
                    requested_at_utc=requested_at,
                    question=question,
                    prompt="Testprompt",
                    hits=[],
                    response_text="Testantwort",
                    citations={"cited": [], "unknown": []},
                )
                ids.append(run_id)

            runs = list_doc_runs(database_path, limit=2)

            # Der Vergleich prüft zugleich Reihenfolge und Anzahl.
            self.assertEqual([run["id"] for run in runs], [ids[2], ids[1]])

            # Die Übersicht enthält nur die vier vereinbarten Felder.
            self.assertEqual(runs[0], {
                "id": ids[2],
                "question": "Dritte Frage",
                "model": "gpt-test",
                "requested_at_utc": "2026-11-15T10:00:00+00:00",
            })