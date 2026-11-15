import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from doc_storage import initialize_doc_database, save_doc_run


class ShowDocRunTests(unittest.TestCase):
    def test_shows_saved_excerpt_even_when_source_file_is_missing(self):
        """Die Laufansicht liest den damaligen Ausschnitt aus SQLite."""
        with tempfile.TemporaryDirectory() as folder:
            work_dir = Path(folder)
            database_path = work_dir / "runs.sqlite3"
            initialize_doc_database(database_path)

            # Diese Quelldatei legen wir absichtlich nicht an.
            # Ihr damaliger Inhalt steht nur im gespeicherten Lauf.
            source_path = "docs/hardware.md"
            location = f"{source_path}:3-5"
            excerpt = "CPU: Intel Core i5-8500 (6 Kerne)"
            prompt = f"Frage: Welche CPU?\nFundstelle: {location}\n{excerpt}"
            answer = f"Intel Core i5-8500. (Fundstelle: {location})"

            run_id = save_doc_run(
                database_path,
                model="gpt-test",
                requested_at_utc="2026-11-15T09:00:00+00:00",
                question="Welche CPU?",
                prompt=prompt,
                hits=[{
                    "path": source_path,
                    "start_line": 3,
                    "end_line": 5,
                    "text": excerpt,
                }],
                response_text=answer,
                citations={"cited": [location], "unknown": []},
                api_status="completed",
            )

            # Starte den echten Terminalbefehl im temporären Ordner.
            # --database verweist auf die Testdatei statt auf deine lokale DB.
            script = Path(__file__).resolve().parents[1] / "show_doc_run.py"
            result = subprocess.run(
                [sys.executable, str(script), str(run_id),
                 "--database", str(database_path)],
                cwd=work_dir,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Gesendeter Prompt:\n{prompt}\n", result.stdout)
            self.assertIn(f"Fundstelle 1: {location}\n{excerpt}\n", result.stdout)
            self.assertIn(f"Antwort:\n{answer}\n", result.stdout)
            self.assertIn("Unbekannte Fundstellen: keine", result.stdout)