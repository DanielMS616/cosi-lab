import subprocess
import sys
import tempfile
import unittest

from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from types import ModuleType
from unittest.mock import Mock, patch

from doc_search import main


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


    def test_no_match_skips_the_model_call(self):
        """Auch mit --gpt wird ohne Fundstelle kein Modell aufgerufen."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fernzugriff.md"
            path.write_text("SSH läuft im WireGuard-Tunnel.\n", encoding="utf-8")

            # Ersetze das echte GPT-Modul durch ein Testobjekt.
            # Mock merkt sich Aufrufe, ohne eine API anzusprechen.
            fake_gpt = ModuleType("model_gpt")
            fake_gpt.generate_gpt_report = Mock(return_value={"text": "Testantwort"})

            # Übergib main() dieselben Argumente wie beim Terminalaufruf.
            argv = ["doc_search.py", str(path), "Kartoffelsalat?", "--question", "--gpt"]
            output = StringIO()
            with (
                patch.dict(sys.modules, {"model_gpt": fake_gpt}),
                patch.object(sys, "argv", argv),
                redirect_stdout(output),
            ):
                main()

            fake_gpt.generate_gpt_report.assert_not_called()
            self.assertEqual(output.getvalue(), "Keine passende Fundstelle gefunden.\n")