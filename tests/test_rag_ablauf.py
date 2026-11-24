import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rag_ablauf import beantworte_und_speichere
from rag_prompt import baue_prompt
from rag_run_storage import load_rag_run


class RagAblaufTests(unittest.TestCase):
    def test_meldet_unbekanntes_zitat_und_speichert_den_lauf(self):
        frage = "Wie breit soll die Halterung H-12 sein?"
        datei = "examples/rag/masspruefung-h12.md"

        # Gib zwei vorbereitete Treffer vor. E5 und PostgreSQL sind dafür unnötig.
        fundstellen = [
            {
                "datei": datei,
                "startzeile": 6,
                "endzeile": 7,
                "text": "Das Sollmaß steht in einer separaten Zeichnung.",
                "wert": 0.822,
            },
            {
                "datei": datei,
                "startzeile": 3,
                "endzeile": 4,
                "text": "Die Halterung liegt vor der Prüfung im Messraum.",
                "wert": 0.812,
            },
        ]
        prompt = baue_prompt(frage, fundstellen)

        # Die Datei stimmt in beiden Zitaten. Nur der zweite Zeilenbereich
        # stand nicht im Prompt und soll deshalb als unbekannt gemeldet werden.
        unbekanntes_zitat = f"{datei}:6-8"
        modellantwort = {
            "text": f"Siehe Zeichnung ({datei}:6-7, {unbekanntes_zitat}).",
            "model": "gpt-test",
            "requested_at_utc": "2026-11-24T08:00:00.000+00:00",
            "client_duration_ms": 120,
        }

        # SQLite schreibt in einen Testordner, der danach gelöscht wird.
        with TemporaryDirectory() as ordner:
            datenbank = Path(ordner) / "rag-test.sqlite3"

            # patch ersetzt nur den Modellaufruf und nur innerhalb dieses Blocks.
            # Zitatprüfung und Speicherung verwenden weiterhin den echten Code.
            with patch(
                "rag_ablauf.rufe_antwortmodell_auf", return_value=modellantwort
            ) as modellaufruf:
                antwortdaten, zitatpruefung, lauf_id = beantworte_und_speichere(
                    frage,
                    prompt,
                    fundstellen,
                    anbieter="gpt",
                    top_k=2,
                    suchmodell="e5-test",
                    e5_load_ms=0,
                    retrieval_ms=0,
                    database_path=datenbank,
                )
                modellaufruf.assert_called_once_with(
                    prompt, "gpt", max_output_tokens=240
                )

            # Lies den Lauf wie später show_rag_run.py über die Lauf-ID zurück.
            lauf = load_rag_run(datenbank, lauf_id)

        self.assertEqual(antwortdaten["text"], modellantwort["text"])
        self.assertEqual(zitatpruefung["unbekannt"], [unbekanntes_zitat])
        self.assertIsNotNone(lauf)
        self.assertEqual(lauf["prompt"], prompt)
        self.assertEqual(lauf["response_text"], modellantwort["text"])
        self.assertEqual(lauf["sources"], fundstellen)