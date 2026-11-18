import tempfile
import unittest
from pathlib import Path

from doc_chunks import split_document


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