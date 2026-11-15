import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

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