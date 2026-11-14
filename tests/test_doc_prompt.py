import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DocPromptTests(unittest.TestCase):
    def test_preview_shows_original_question_source_and_excerpt(self):
        """Die Vorschau zeigt die Frage und die dazu gefundene Quelle."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fernzugriff.md"
            excerpt = "WireGuard-Endpunkt\nSSH-Anmeldung\nSSH läuft im Tunnel."
            path.write_text(excerpt, encoding="utf-8")
            question = "Wie funktioniert SSH im WireGuard-Tunnel?"

            # Starte die CLI mit demselben Python wie den Test.
            script = Path(__file__).resolve().parents[1] / "doc_search.py"
            result = subprocess.run(
                [sys.executable, str(script), str(path), question,
                 "--question", "--show-prompt"],
                capture_output=True,
                text=True,
            )

            # Prüfe die Inhalte, auf die es ankommt. Der Wortlaut
            # der Anweisungen im Prompt darf sich später ändern.
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Frage: {question}\n", result.stdout)
            self.assertIn(f"Fundstelle: {path}:1-3\n", result.stdout)
            self.assertIn(f"Ausschnitt:\n{excerpt}\n", result.stdout)