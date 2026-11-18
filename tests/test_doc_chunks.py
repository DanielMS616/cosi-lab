import tempfile
import unittest
from pathlib import Path

from doc_chunks import split_document, split_chunk_by_lines


class DocChunksTests(unittest.TestCase):
    def setUp(self):
        # Jeder Test erhält einen eigenen temporären Ordner.
        # Die echten Projektdokumente bleiben unverändert.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "document.md"

    def test_code_block_keeps_blank_lines_and_source_location(self):
        """Ein Diagramm bleibt trotz Leerzeile ein vollständiger Abschnitt."""
        self.path.write_text(
            "# Hardware\n"
            "\n"
            "```mermaid\n"
            "flowchart TB\n"
            "\n"
            'RAM["16 GB DDR4 (2 Module)"]\n'
            "```\n",
            encoding="utf-8",
        )

        chunks = split_document(self.path)

        # Die Leerzeile innerhalb des Diagramms darf es nicht aufteilen.
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]

        # Überschrift und Fundstelle gehören zum ursprünglichen Dokument.
        self.assertEqual(chunk["path"], str(self.path))
        self.assertEqual(chunk["heading"], "Hardware")
        self.assertEqual(chunk["start_line"], 3)
        self.assertEqual(chunk["end_line"], 7)

        # Auch die Codezäune und die innere Leerzeile bleiben erhalten.
        self.assertEqual(
            chunk["text"],
            "```mermaid\n"
            "flowchart TB\n"
            "\n"
            'RAM["16 GB DDR4 (2 Module)"]\n'
            "```",
        )

    def test_table_stays_together_and_separator_is_skipped(self):
        """Eine Tabelle bleibt zusammen; eine einzelne Trennlinie entfällt."""
        table = (
            "| Bauteil | Anzahl |\n"
            "| --- | --- |\n"
            "| RAM | 2 |"
        )
        self.path.write_text(
            "# Übersicht\n\n" + table + "\n\n---\n",
            encoding="utf-8",
        )

        chunks = split_document(self.path)

        # Die zusätzliche Trennlinie erzeugt keinen eigenen Abschnitt.
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["text"], table)
        self.assertEqual(chunks[0]["heading"], "Übersicht")
        self.assertEqual(chunks[0]["start_line"], 3)
        self.assertEqual(chunks[0]["end_line"], 5)

    def test_last_paragraph_is_kept_without_final_newline(self):
        """Der letzte Absatz geht ohne abschließenden Zeilenumbruch nicht verloren."""
        self.path.write_text(
            "# Export\n\nBestätige mit ja.",
            encoding="utf-8",
        )

        chunks = split_document(self.path)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["text"], "Bestätige mit ja.")
        self.assertEqual(chunks[0]["heading"], "Export")
        self.assertEqual(chunks[0]["start_line"], 3)
        self.assertEqual(chunks[0]["end_line"], 3)

    def test_parts_keep_all_lines_and_fit_budget(self):
        """Alle Zeilen bleiben erhalten und jeder Teil hält das Testbudget ein."""
        chunk = {
            "path": "probe.md",
            "heading": "Beispiel",
            "start_line": 10,
            "end_line": 12,
            "text": "eins zwei\ndrei vier\nfünf sechs",
        }

        def count_tokens(text):
            # Einfaches Zählverfahren für diesen Test:
            # Jedes Wort zählt einmal, dazu kommen zwei feste Zusatzkosten.
            # Das ersetzt hier den echten Tokenizer.
            return len(text.split()) + 2

        parts = split_chunk_by_lines(chunk, count_tokens, max_tokens=6)

        self.assertEqual(len(parts), 2)
        self.assertEqual(
            [
                (part["start_line"], part["end_line"])
                for part in parts
            ],
            [(10, 11), (12, 12)],
        )

        # Zusammengesetzt müssen die Teile wieder den Originaltext ergeben.
        self.assertEqual(
            "\n".join(part["text"] for part in parts),
            chunk["text"],
        )

        for part in parts:
            self.assertLessEqual(count_tokens(part["text"]), 6)
            self.assertEqual(part["path"], chunk["path"])
            self.assertEqual(part["heading"], chunk["heading"])

    def test_short_chunk_is_kept_unchanged(self):
        """Ein kurzer Abschnitt wird als vollständige Kopie geliefert."""
        chunk = {
            "path": "probe.md",
            "heading": "Beispiel",
            "start_line": 4,
            "end_line": 5,
            "text": "eins\nzwei",
        }

        # len zählt hier Zeichen und dient als einfache Test-Zählfunktion.
        parts = split_chunk_by_lines(chunk, len, max_tokens=20)

        self.assertEqual(parts, [chunk])
        self.assertIsNot(parts[0], chunk)

    def test_single_long_line_raises(self):
        """Eine einzelne überlange Zeile erzeugt eine verständliche Meldung."""
        chunk = {
            "path": "probe.md",
            "heading": "Beispiel",
            "start_line": 8,
            "end_line": 8,
            "text": "zu lang",
        }

        # Sieben Zeichen passen nicht in das kleine Testbudget von drei.
        with self.assertRaisesRegex(ValueError, "Zeile 8"):
            split_chunk_by_lines(chunk, len, max_tokens=3)