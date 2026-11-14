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


    def test_project_docs_preview_finds_source_without_a_file_argument(self):
        """Mit --project-docs findet die Vorschau die Quelle ohne Dateipfad."""
        project_dir = Path(__file__).resolve().parents[1]
        question = "Wie funktioniert SSH im WireGuard-Tunnel?"

        # Der Befehl bekommt eine Frage, aber keinen Pfad zu einem Dokument.
        # cwd setzt den Projektordner, damit die relativen docs/-Pfade stimmen.
        result = subprocess.run(
            [
                sys.executable,
                str(project_dir / "doc_search.py"),
                question,
                "--project-docs",
                "--show-prompt",
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"Frage: {question}\n", result.stdout)
        self.assertIn("Fundstelle: docs/aufbau-fernzugriff.md:", result.stdout)
        self.assertIn("SSH im Tunnel", result.stdout)


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


    def test_multi_source_adds_the_second_source_only_when_requested(self):
        """Die Promptvorschau enthält nur mit --multi-source beide Quellen."""
        with tempfile.TemporaryDirectory() as folder:
            hardware = Path(folder) / "hardware.md"
            remote = Path(folder) / "fernzugriff.md"

            # Jede Datei beantwortet nur einen Teil der Frage.
            hardware_text = "CPU: Intel Core i5-8500"
            remote_text = (
                "WireGuard-Endpunkt\n"
                "SSH-Anmeldung mit Schlüssel\n"
                "SSH läuft im Tunnel."
            )
            hardware.write_text(hardware_text, encoding="utf-8")
            remote.write_text(remote_text, encoding="utf-8")

            script = Path(__file__).resolve().parents[1] / "doc_search.py"
            command = [
                sys.executable,
                str(script),
                str(hardware),
                "Welche CPU ist verbaut und wie läuft SSH im WireGuard-Tunnel?",
                "--question",
                "--also-search", str(remote),
                "--show-prompt",
            ]

            # Gleiche Frage, gleiche Dateien. Nur der Schalter ändert sich.
            single = subprocess.run(command, capture_output=True, text=True)
            multi = subprocess.run(
                command + ["--multi-source"], capture_output=True, text=True
            )

            self.assertEqual(single.returncode, 0, single.stderr)
            self.assertIn(f"Fundstelle: {remote}:1-3\n", single.stdout)
            self.assertNotIn(hardware_text, single.stdout)

            self.assertEqual(multi.returncode, 0, multi.stderr)
            self.assertIn(
                f"Fundstelle 1: {remote}:1-3\nAusschnitt:\n{remote_text}",
                multi.stdout,
            )
            self.assertIn(
                f"Fundstelle 2: {hardware}:1-1\nAusschnitt:\n{hardware_text}",
                multi.stdout,
            )