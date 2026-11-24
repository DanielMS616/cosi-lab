import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from modell_fehler import (
    ModellschluesselFehlt,
    ModellverbindungFehlgeschlagen,
    ModellzeitUeberschritten,
)
from rag_api import app


FRAGE = "Wie breit soll die Halterung H-12 sein?"
DATEI = "examples/rag/masspruefung-h12.md"
BELEG = f"{DATEI}:6-7"
FUNDSTELLEN = [
    {
        "datei": DATEI,
        "startzeile": 6,
        "endzeile": 7,
        "text": "Das Sollmaß steht in einer separaten Zeichnung.",
        "wert": 0.822,
    }
]


class RagApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Jeder Test bekommt eine eigene SQLite-Datei im temporären Ordner.
        ordner = TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        self.datenbank = Path(ordner.name) / "rag-test.sqlite3"

        # HTTPX leitet Anfragen direkt an FastAPI weiter. Kein Serverstart nötig.
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_antwort_laesst_sich_ueber_lauf_id_abrufen(self):
        modellantwort = {
            "text": f"Nicht belegt: Sollbreite.\nHinweis: Siehe Zeichnung ({BELEG}).",
            "model": "gpt-test",
            "requested_at_utc": "2026-11-24T09:00:00+00:00",
            "client_duration_ms": 100,
        }

        # Simuliere die Suche und den Anbieter. Speichern und Lesen bleiben echt.
        with (
            patch("rag_api.RUN_DATABASE", self.datenbank),
            patch("rag_api.suche_fuer_api", return_value=(FUNDSTELLEN, 200, 30)),
            patch("rag_ablauf.rufe_antwortmodell_auf", return_value=modellantwort),
        ):
            post = await self.client.post(
                "/rag/antwort", json={"frage": FRAGE, "top_k": 1, "anbieter": "gpt"}
            )
            self.assertEqual(post.status_code, 200, post.text)
            antwort = post.json()
            self.assertIsInstance(antwort["lauf_id"], int)
            self.assertIn(BELEG, antwort["prompt"])
            self.assertEqual(antwort["zitatpruefung"]["erkannt"], [BELEG])

            # Verwende genau die Lauf-ID, die der POST-Endpunkt zurückgab.
            get = await self.client.get(f"/rag/laeufe/{antwort['lauf_id']}")
            self.assertEqual(get.status_code, 200, get.text)
            lauf = get.json()

        self.assertEqual(lauf["prompt"], antwort["prompt"])
        self.assertEqual(lauf["response_text"], modellantwort["text"])
        self.assertEqual(lauf["sources"], FUNDSTELLEN)

    async def test_ohne_fundstellen_keine_modellantwort_und_kein_lauf(self):
        with (
            patch("rag_api.RUN_DATABASE", self.datenbank),
            patch("rag_api.suche_fuer_api", return_value=([], 200, 30)),
            patch("rag_ablauf.rufe_antwortmodell_auf") as modellaufruf,
        ):
            post = await self.client.post(
                "/rag/antwort", json={"frage": FRAGE, "anbieter": "gpt"}
            )
            self.assertEqual(post.status_code, 200, post.text)
            antwort = post.json()

            # Die leere Suche darf weder einen Modellaufruf noch einen Lauf auslösen.
            self.assertEqual(antwort["fundstellen"], [])
            self.assertIsNone(antwort["antwort"])
            self.assertIsNone(antwort["lauf_id"])
            modellaufruf.assert_not_called()
            self.assertFalse(self.datenbank.exists())

    async def test_fehlender_modellschluessel_liefert_503_ohne_lauf(self):
        for anbieter, variable in (("gpt", "OPENAI_API_KEY"), ("gemini", "GEMINI_API_KEY")):
            with self.subTest(anbieter=anbieter):
                meldung = f"{variable} fehlt. Prüfe die lokale .env."
                # Simuliere nur den Fehler. Die echte .env bleibt unangetastet.
                with (
                    patch("rag_api.RUN_DATABASE", self.datenbank),
                    patch("rag_api.suche_fuer_api", return_value=(FUNDSTELLEN, 200, 30)),
                    patch(
                        "rag_ablauf.rufe_antwortmodell_auf",
                        side_effect=ModellschluesselFehlt(meldung),
                    ),
                ):
                    post = await self.client.post(
                        "/rag/antwort", json={"frage": FRAGE, "anbieter": anbieter}
                    )

                self.assertEqual(post.status_code, 503, post.text)
                self.assertEqual(post.json(), {"detail": meldung})
                self.assertFalse(self.datenbank.exists())

    async def test_netzwerkfehler_und_zeitlimit_werden_unterschieden(self):
        # Der simulierte Fehler entsteht an derselben Stelle wie ein SDK-Fehler.
        # Die Antwort und die Speicherung durchlaufen den echten API-Code.
        faelle = (
            (ModellverbindungFehlgeschlagen("Verbindung fehlgeschlagen."), 502),
            (ModellzeitUeberschritten("Zeitlimit überschritten."), 504),
        )
        for fehler, status in faelle:
            with self.subTest(status=status):
                with (
                    patch("rag_api.RUN_DATABASE", self.datenbank),
                    patch("rag_api.suche_fuer_api", return_value=(FUNDSTELLEN, 200, 30)),
                    patch("rag_ablauf.rufe_antwortmodell_auf", side_effect=fehler),
                ):
                    post = await self.client.post(
                        "/rag/antwort", json={"frage": FRAGE, "anbieter": "gpt"}
                    )

                self.assertEqual(post.status_code, status, post.text)
                self.assertEqual(post.json(), {"detail": str(fehler)})
                self.assertFalse(self.datenbank.exists())

    async def test_laufuebersicht_zeigt_neueste_laeufe_und_beachtet_limit(self):
        modellantwort = {
            "text": "Nicht belegt: Sollbreite.",
            "model": "gpt-test",
            "requested_at_utc": "2026-11-24T09:00:00+00:00",
            "client_duration_ms": 100,
        }

        # Speichere zwei Läufe über die API. Beide bekommen denselben Zeitstempel,
        # damit wir prüfen können, ob die Übersicht nach Lauf-ID sortiert.
        with (
            patch("rag_api.RUN_DATABASE", self.datenbank),
            patch("rag_api.suche_fuer_api", return_value=(FUNDSTELLEN, 200, 30)),
            patch("rag_ablauf.rufe_antwortmodell_auf", return_value=modellantwort),
        ):
            ids = []
            for frage in (FRAGE, "Was steht in der Zeichnung?"):
                post = await self.client.post(
                    "/rag/antwort", json={"frage": frage, "anbieter": "gpt"}
                )
                self.assertEqual(post.status_code, 200, post.text)
                ids.append(post.json()["lauf_id"])

            alle = await self.client.get("/rag/laeufe")
            einzeln = await self.client.get("/rag/laeufe?limit=1")
            ungueltig = await self.client.get("/rag/laeufe?limit=0")

        self.assertEqual(alle.status_code, 200, alle.text)
        laeufe = alle.json()["laeufe"]
        self.assertEqual([lauf["id"] for lauf in laeufe], [ids[1], ids[0]])
        self.assertEqual(einzeln.status_code, 200, einzeln.text)
        self.assertEqual(einzeln.json()["laeufe"], laeufe[:1])
        self.assertEqual(
            set(laeufe[0]), {"id", "question", "provider", "model", "requested_at_utc"}
        )
        self.assertEqual(ungueltig.status_code, 422, ungueltig.text)

    async def test_leere_laufuebersicht_legt_keine_datenbank_an(self):
        with patch("rag_api.RUN_DATABASE", self.datenbank):
            antwort = await self.client.get("/rag/laeufe")

        self.assertEqual(antwort.status_code, 200, antwort.text)
        self.assertEqual(antwort.json(), {"laeufe": []})
        self.assertFalse(self.datenbank.exists())
