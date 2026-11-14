import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from model_storage import initialize_database, save_model_run


class ReportExportTests(unittest.TestCase):
    """Prüft den Berichtsexport so, wie er im Terminal aufgerufen wird."""

    def setUp(self):
        # unittest ruft setUp() vor jedem Test auf. So bekommt jeder Test
        # einen eigenen Ordner und eine eigene Datenbank.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)  # Räumt auch bei einem fehlgeschlagenen Test auf.
        self.work_dir = Path(folder.name)
        self.database = self.work_dir / "runs.sqlite3"

        # Der feste Antworttext enthält ein Gradzeichen und einen Zeilenumbruch.
        # So können wir später prüfen, ob beides unverändert exportiert wird.
        self.answer = "Ein Messwert liegt über 60 °C.\nEin Messwert fehlt."

        # Diese Testdatei liegt in tests/. parents[1] ist der Projektordner.
        # Der absolute Pfad findet das Skript auch aus dem temporären Ordner.
        self.script = Path(__file__).resolve().parents[1] / "show_model_run.py"

        # Lege einen Beispiel-Modelllauf an. Dafür ist kein API-Aufruf nötig.
        initialize_database(self.database)
        self.run_id = save_model_run(
            self.database, "demo", "beispiel.csv", 60, "Beispielprompt", self.answer
        )
        self.target = self.work_dir / "reports" / f"model-run-{self.run_id}.txt"

    def run_export(self, reply):
        """Startet den Export und beantwortet die Rückfrage automatisch."""
        return subprocess.run(
            # Verwende denselben Python-Interpreter, der auch den Test ausführt.
            [
                sys.executable, str(self.script), str(self.run_id),
                "--database", str(self.database), "--export",
            ],
            cwd=self.work_dir,  # Der relative Ordner reports/ entsteht hier.
            input=f"{reply}\n",  # \n entspricht dem Drücken der Enter-Taste.
            text=True,
            capture_output=True,  # Normale Ausgabe in stdout, Fehler in stderr.
        )

    def test_confirmation_exports_only_the_saved_answer(self):
        """Nach 'ja' enthält die Datei exakt den gespeicherten Antworttext."""
        result = self.run_export("ja")

        self.assertEqual(result.returncode, 0, result.stderr)
        # Der Vergleich der Bytes prüft UTF-8 und den genauen Inhalt.
        # Auch ein zusätzliches Leerzeichen oder ein zusätzlicher Umbruch fällt auf.
        self.assertEqual(self.target.read_bytes(), self.answer.encode("utf-8"))

    def test_decline_does_not_create_export_directory(self):
        """Nach 'nein' endet das Programm regulär und legt keinen Ordner an."""
        result = self.run_export("nein")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Export abgelehnt.", result.stdout)
        self.assertFalse(self.target.parent.exists())

    def test_existing_report_is_not_overwritten(self):
        """Ein erneutes 'ja' lässt eine vorhandene Datei unverändert."""
        # Schreibe bewusst einen anderen Inhalt. So würde der letzte
        # Vergleich ein versehentliches Überschreiben erkennen.
        self.target.parent.mkdir()
        self.target.write_bytes(b"Vorhandener Bericht")

        result = self.run_export("ja")

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Ziel bereits belegt", result.stderr)
        self.assertEqual(self.target.read_bytes(), b"Vorhandener Bericht")