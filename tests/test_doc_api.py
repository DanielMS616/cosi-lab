import tempfile
import unittest
import sys

from pathlib import Path
from unittest.mock import patch
from types import ModuleType
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from httpx import Request
from openai import APIConnectionError
from google.genai.errors import ServerError

from doc_storage import initialize_doc_database, load_doc_run, save_doc_run
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

    def test_provider_connection_error_returns_502_without_saving(self):
        # Das Request-Objekt beschreibt nur eine Anfrage. Es wird nichts gesendet.
        error = APIConnectionError(
            request=Request("POST", "https://example.invalid")
        )

        # Die Suche läuft normal. Erst beim Modellaufruf werfen wir den Fehler.
        fake_gpt = ModuleType("model_gpt")
        fake_gpt.generate_gpt_report = Mock(side_effect=error)

        with (
            patch.dict(sys.modules, {"model_gpt": fake_gpt}),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            response = client.post(
                "/doc-questions/answer",
                json={"question": "Welche CPU hat Cosi-Lab?", "provider": "gpt"},
            )

        # So stellen wir sicher, dass die Anfrage wirklich bis zum Modell kam.
        fake_gpt.generate_gpt_report.assert_called_once()
        self.assertFalse(self.database_path.exists())
        self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(
            response.json(),
            {"detail": "Der Modellanbieter ist derzeit nicht erreichbar."},
        )

    def test_read_doc_run_returns_the_saved_data(self):
        # Lege einen festen Lauf in der temporären Testdatenbank an.
        # Dafür brauchen wir weder eine Dokusuche noch ein Modell.
        initialize_doc_database(self.database_path)
        source = {
            "path": "docs/hardware.md",
            "start_line": 5,
            "end_line": 5,
            "text": "CPU: Intel Core i5-8500",
        }
        prompt = "Welche CPU?\nCPU: Intel Core i5-8500"
        answer = "Intel Core i5-8500. (Fundstelle: docs/hardware.md:5-5)"
        citations = {"cited": ["docs/hardware.md:5-5"], "unknown": []}
        run_id = save_doc_run(
            self.database_path,
            model="gpt-test",
            requested_at_utc="2026-11-15T12:00:00+00:00",
            question="Welche CPU?",
            prompt=prompt,
            hits=[source],
            response_text=answer,
            citations=citations,
            api_status="completed",
        )

        # Rufe den Lauf über die echte HTTP-Route ab.
        response = self.client.get(f"/doc-runs/{run_id}")

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["id"], run_id)
        self.assertEqual(data["prompt"], prompt)
        self.assertEqual(data["response_text"], answer)
        self.assertEqual(data["sources"], [source])
        self.assertEqual(data["citations"], citations)

    def test_read_unknown_doc_run_returns_404(self):
        # Die Tabelle existiert und ist lesbar. Nur der Lauf fehlt.
        initialize_doc_database(self.database_path)

        response = self.client.get("/doc-runs/99999")

        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(
            response.json(), {"detail": "Kein Dokulauf mit ID 99999 gefunden."}
        )

    def test_list_doc_runs_respects_the_requested_limit(self):
        initialize_doc_database(self.database_path)

        # Drei Einträge machen den Unterschied zwischen dem angeforderten
        # Limit von zwei und dem Standardlimit von zehn sichtbar.
        ids = []
        for question in ("Erste Frage", "Zweite Frage", "Dritte Frage"):
            ids.append(save_doc_run(
                self.database_path,
                model="gpt-test",
                requested_at_utc="2026-11-15T12:00:00+00:00",
                question=question,
                prompt="Testprompt",
                hits=[],
                response_text="Testantwort",
                citations={"cited": [], "unknown": []},
            ))

        response = self.client.get("/doc-runs?limit=2")

        self.assertEqual(response.status_code, 200, response.text)
        runs = response.json()["runs"]
        self.assertEqual([run["id"] for run in runs], [ids[2], ids[1]])
        self.assertEqual(
            set(runs[0]), {"id", "question", "model", "requested_at_utc"}
        )

    def test_invalid_run_list_limit_is_rejected_before_reading(self):
        # Prüfe beide Grenzen. Die SQLite-Funktion darf nie erreicht werden.
        with patch("doc_api.list_doc_runs") as list_runs:
            for limit in (0, 101):
                with self.subTest(limit=limit):
                    response = self.client.get(f"/doc-runs?limit={limit}")
                    self.assertEqual(response.status_code, 422, response.text)

        list_runs.assert_not_called()

    def test_gemini_unavailable_returns_503_without_saving(self):
        # Simuliere eine 503-Antwort von Gemini, ohne eine Anfrage zu senden.
        error = ServerError(
            503,
            {"error": {"message": "Simulierter Ausfall", "status": "UNAVAILABLE"}},
        )
        fake_gemini = ModuleType("model_gemini")
        fake_gemini.GEMINI_MODEL = "gemini-test"
        fake_gemini.generate_gemini_report = Mock(side_effect=error)

        with (
            patch.dict(sys.modules, {"model_gemini": fake_gemini}),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            response = client.post(
                "/doc-questions/answer",
                json={"question": "Welche CPU hat Cosi-Lab?", "provider": "gemini"},
            )

        # Die Suche hat einen Treffer geliefert und Gemini ausgewählt.
        # Nach dem Fehler darf trotzdem kein Lauf gespeichert werden.
        fake_gemini.generate_gemini_report.assert_called_once()
        self.assertFalse(self.database_path.exists())
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(
            response.json(),
            {"detail": "Gemini ist vorübergehend nicht verfügbar."},
        )