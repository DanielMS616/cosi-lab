import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
from types import ModuleType
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from doc_storage import load_doc_run
from doc_api import app


class DocApiTests(unittest.TestCase):
    def setUp(self):
        # Kleine, feste Testdateien halten die Tests unabhängig von Änderungen
        # an der echten Projektdoku. unittest räumt den Ordner danach auf.
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.hardware = folder / "hardware.md"
        self.remote = folder / "fernzugriff.md"
        self.hardware.write_text("CPU: Intel Core i5-8500\n", encoding="utf-8")
        self.remote.write_text("SSH läuft im WireGuard-Tunnel.\n", encoding="utf-8")

        self.enterContext(
            patch("doc_api.PROJECT_DOCS", (self.hardware, self.remote))
        )
        # Auch der Antwort-Endpunkt schreibt nur in den temporären Testordner.
        self.database_path = folder / "runs.sqlite3"
        self.enterContext(patch("doc_api.DOC_DATABASE_PATH", self.database_path))
        self.client = self.enterContext(TestClient(app))

    def test_preview_returns_both_sources_in_ranked_order(self):
        response = self.client.post(
            "/doc-questions/preview",
            json={
                "question": "Welche CPU ist verbaut und wie läuft SSH im WireGuard-Tunnel?",
                "multi_source": True,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()

        # Hardware steht in der Dateiliste zuerst. Fernzugriff muss trotzdem
        # vorne stehen, weil sein Ausschnitt mehr Suchwörter trifft.
        self.assertEqual(
            [source["path"] for source in data["sources"]],
            [str(self.remote), str(self.hardware)],
        )
        self.assertIn("SSH läuft im WireGuard-Tunnel.", data["prompt"])
        self.assertIn("CPU: Intel Core i5-8500", data["prompt"])

    def test_no_match_returns_an_empty_result(self):
        question = "Welche Seriennummer hat Cosi-Lab?"
        response = self.client.post(
            "/doc-questions/preview", json={"question": question}
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {
            "question": question, "sources": [], "prompt": None,
        })

    def test_whitespace_question_is_rejected_before_search(self):
        # Die Anfrage enthält gültiges JSON. Unsere Prüfung soll sie
        # ablehnen, bevor die Suche überhaupt gestartet wird.
        with patch("doc_api.find_top_excerpts_in_files") as search:
            response = self.client.post(
                "/doc-questions/preview", json={"question": "   "}
            )

        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(
            response.json()["detail"], "Die Frage darf nicht leer sein."
        )
        search.assert_not_called()

    def test_answer_sends_the_previewed_prompt_and_returns_a_saved_run_id(self):
        question = "Welche CPU hat Cosi-Lab?"
        answer = f"Intel Core i5-8500. (Fundstelle: {self.hardware}:1-1)"
        fake_gpt = ModuleType("model_gpt")
        fake_gpt.generate_gpt_report = Mock(return_value={
            "text": answer,
            "status": "completed",
            "incomplete_reason": None,
        })

        # Nur GPT ist ersetzt. HTTP-Aufruf, Suche und SQLite laufen echt.
        with patch.dict(sys.modules, {"model_gpt": fake_gpt}):
            preview = self.client.post(
                "/doc-questions/preview", json={"question": question}
            )
            response = self.client.post(
                "/doc-questions/answer",
                json={"question": question, "provider": "gpt"},
            )

        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        expected_prompt = preview.json()["prompt"]
        fake_gpt.generate_gpt_report.assert_called_once_with(
            expected_prompt, max_output_tokens=240
        )

        # Die ID aus dem HTTP-Ergebnis muss zu einem lesbaren Lauf führen.
        run = load_doc_run(self.database_path, data["run_id"])
        self.assertIsNotNone(run)
        self.assertEqual(run["prompt"], expected_prompt)
        self.assertEqual(data["answer"], answer)
        self.assertEqual(run["response_text"], answer)

    def test_answer_without_sources_skips_the_model_and_storage(self):
        with patch("doc_api.answer_and_save_doc_question") as answer_and_save:
            response = self.client.post(
                "/doc-questions/answer",
                json={
                    "question": "Welche Seriennummer hat Cosi-Lab?",
                    "provider": "gpt",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["sources"], [])
        self.assertIsNone(data["answer"])
        self.assertIsNone(data["run_id"])
        answer_and_save.assert_not_called()
        self.assertFalse(self.database_path.exists())