import tempfile
import unittest
from pathlib import Path

from doc_search import find_best_excerpt, find_best_excerpt_in_files


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


    def test_later_file_wins_when_it_matches_more_terms(self):
        """Die zweite Datei gewinnt, wenn sie mehr Suchwörter trifft."""
        with tempfile.TemporaryDirectory() as folder:
            first_path = Path(folder) / "uebersicht.md"
            second_path = Path(folder) / "fernzugriff.md"

            # Die erste Datei trifft bereits ein Suchwort: SSH.
            first_path.write_text("SSH ist verfügbar.\n", encoding="utf-8")

            # Die zweite Datei trifft alle drei: SSH, WireGuard und Tunnel.
            second_path.write_text(
                "WireGuard-Endpunkt\n"
                "SSH-Anmeldung mit Schlüssel\n"
                "Die Verbindung läuft im Tunnel.\n",
                encoding="utf-8",
            )

            hit = find_best_excerpt_in_files(
                [first_path, second_path],
                "Wie funktioniert SSH im WireGuard-Tunnel?",
            )

            self.assertIsNotNone(hit)
            self.assertEqual(hit["path"], str(second_path))
            self.assertEqual(hit["matched_terms"], ["ssh", "tunnel", "wireguard"])