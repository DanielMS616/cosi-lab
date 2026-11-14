import tempfile
import unittest
from pathlib import Path

from doc_search import find_best_excerpt


class DocSearchTests(unittest.TestCase):
    def test_later_excerpt_wins_when_it_matches_more_terms(self):
        """Ein späterer Ausschnitt mit mehr Suchwörtern gewinnt."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fernzugriff.md"

            # Zeile 1 enthält bereits einen Treffer für SSH.
            # Erst die Zeilen 4–6 enthalten alle drei Suchwörter.
            path.write_text(
                "SSH ist ein Protokoll.\n"
                "Hinweise zur Einrichtung\n"
                "Weitere Informationen\n"
                "WireGuard-Endpunkt\n"
                "SSH-Anmeldung mit Schlüssel\n"
                "SSH läuft im Tunnel.\n",
                encoding="utf-8",
            )

            hit = find_best_excerpt(path, "Wie funktioniert SSH im WireGuard-Tunnel?")

            # Ohne Treffer soll der Test hier mit einer klaren Meldung scheitern.
            self.assertIsNotNone(hit)
            self.assertEqual((hit["start_line"], hit["end_line"]), (4, 6))
            self.assertEqual(hit["matched_terms"], ["ssh", "tunnel", "wireguard"])