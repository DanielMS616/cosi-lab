import subprocess
import sys
import tempfile
import unittest
import json
import sqlite3

from contextlib import closing, redirect_stdout
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from types import ModuleType
from unittest.mock import Mock, patch

from doc_search import main

class DocPromptTests(unittest.TestCase):
    def setUp(self):
        # Jeder Test bekommt einen eigenen temporären Datenbankpfad.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.database_path = Path(folder.name) / "runs.sqlite3"

        # Wenn der Test main() direkt aufruft, verwendet es diesen Pfad.
        # Nach dem Test stellt unittest den normalen Pfad wieder her.
        self.enterContext(
            patch("doc_search.DOC_DATABASE_PATH", self.database_path)
        )


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
            self.assertFalse(self.database_path.exists())


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


    def test_gpt_output_warns_about_a_citation_not_in_the_prompt(self):
        """Nur die abweichende Fundstelle erscheint in der Warnung."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "hardware.md"
            path.write_text("CPU: Intel Core i5-8500\n", encoding="utf-8")

            known = f"{path}:1-1"
            unknown = f"{path}:1-4"

            # Die API-Antwort ist absichtlich vollständig, enthält aber
            # eine falsche Quellenangabe. So prüfen wir nur die Zitatwarnung.
            fake_gpt = ModuleType("model_gpt")
            fake_gpt.generate_gpt_report = Mock(return_value={
                "text": f"CPU: Intel Core i5-8500. Quelle: {known}\n"
                        f"Weitere Details: {unknown}",
                "status": "completed",
                "incomplete_reason": None,
            })

            argv = ["doc_search.py", str(path), "Welche CPU?", "--question", "--gpt"]
            output = StringIO()
            with (
                patch.dict(sys.modules, {"model_gpt": fake_gpt}),
                patch.object(sys, "argv", argv),
                redirect_stdout(output),
            ):
                main()

            # Prüfe die Warnliste, nicht nur das Vorkommen im Antworttext.
            self.assertIn("Fundstellen, die nicht im Prompt standen:\n", output.getvalue())
            self.assertIn(f"- {unknown}\n", output.getvalue())
            self.assertNotIn(f"- {known}\n", output.getvalue())


    def test_gpt_and_gemini_receive_the_same_doc_prompt(self):
        """Der Modellschalter ändert den Anbieter, aber nicht den Prompt."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "hardware.md"
            path.write_text("CPU: Intel Core i5-8500\n", encoding="utf-8")
            question = "Welche CPU ist verbaut?"
            answer = f"Intel Core i5-8500 (Fundstelle: {path}:1-1)."

            # Beide Testmodule merken sich ihre Aufrufe. Sie senden nichts.
            fake_gpt = ModuleType("model_gpt")
            gpt_call = fake_gpt.generate_gpt_report = Mock(return_value={
                "text": answer,
                "status": "completed",
                "incomplete_reason": None,
            })
            fake_gemini = ModuleType("model_gemini")
            fake_gemini.GEMINI_MODEL = "gemini-test"
            gemini_call = fake_gemini.generate_gemini_report = Mock(
                return_value={"text": answer}
            )

            # Frage, Datei und Suchart bleiben gleich. Nur der Schalter wechselt.
            argv = ["doc_search.py", str(path), question, "--question"]
            gemini_output = StringIO()

            with patch.dict(sys.modules, {
                "model_gpt": fake_gpt,
                "model_gemini": fake_gemini,
            }):
                with patch.object(sys, "argv", argv + ["--gpt"]), redirect_stdout(StringIO()):
                    main()

                gpt_call.assert_called_once()
                gemini_call.assert_not_called()

                with patch.object(sys, "argv", argv + ["--gemini"]), redirect_stdout(gemini_output):
                    main()

            # args[0] ist der Prompt, den der GPT-Adapter tatsächlich erhalten hat.
            prompt = gpt_call.call_args.args[0]
            self.assertIn(f"Fundstelle: {path}:1-1\n", prompt)
            gpt_call.assert_called_once_with(prompt, max_output_tokens=240)
            gemini_call.assert_called_once_with(prompt, max_output_tokens=240)

            # Auch die Gemini-Antwort läuft durch die gemeinsame Zitatprüfung.
            self.assertIn("Gemini-Antwort:", gemini_output.getvalue())
            self.assertIn(
                "Alle erkannten Fundstellen standen im Prompt.",
                gemini_output.getvalue(),
            )


    def test_doc_run_keeps_the_sent_prompt_and_both_source_excerpts(self):
        """SQLite bewahrt den gesendeten Prompt und die ursprünglichen Quellen."""
        hardware = self.database_path.parent / "hardware.md"
        remote = self.database_path.parent / "fernzugriff.md"
        hardware_text = "CPU: Intel Core i5-8500 (6 Kerne)"
        remote_text = "SSH-Anmeldung mit Schlüssel durch den WireGuard-Tunnel."
        hardware.write_text(hardware_text, encoding="utf-8")
        remote.write_text(remote_text, encoding="utf-8")

        question = "Welche CPU ist verbaut und wie läuft SSH im WireGuard-Tunnel?"
        answer = f"Intel Core i5-8500 (Fundstelle: {hardware}:1-1)."
        fake_gpt = ModuleType("model_gpt")
        fake_gpt.generate_gpt_report = Mock(return_value={
            "text": answer,
            "status": "completed",
            "incomplete_reason": None,
        })

        # Echte Suche und echte Speicherung; nur der Modellaufruf ist ersetzt.
        argv = [
            "doc_search.py", str(hardware), question,
            "--question", "--also-search", str(remote), "--multi-source", "--gpt",
        ]
        with (
            patch.dict(sys.modules, {"model_gpt": fake_gpt}),
            patch.object(sys, "argv", argv),
            redirect_stdout(StringIO()),
        ):
            main()

        # Merke den tatsächlich übergebenen Prompt, statt ihn neu zu bauen.
        fake_gpt.generate_gpt_report.assert_called_once()
        sent_prompt = fake_gpt.generate_gpt_report.call_args.args[0]

        # Ändere die Datei nach dem Lauf. In SQLite muss der alte Text bleiben.
        remote.write_text("Inzwischen geändert.", encoding="utf-8")

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM doc_runs").fetchall()

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["question"], question)
        self.assertEqual(row["prompt"], sent_prompt)
        self.assertEqual(row["response_text"], answer)

        # Fernzugriff trifft mehr Suchwörter und steht deshalb vor Hardware.
        self.assertEqual(json.loads(row["sources_json"]), [
            {"path": str(remote), "start_line": 1, "end_line": 1, "text": remote_text},
            {"path": str(hardware), "start_line": 1, "end_line": 1, "text": hardware_text},
        ])