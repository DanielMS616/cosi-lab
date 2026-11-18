import re
from pathlib import Path


def split_document(path):
    """Teilt eine Markdown-Datei in Absätze und Codeblöcke mit Fundstellen."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()

    # Zuerst sammeln wir die Grenzen der Abschnitte.
    # Jeder Eintrag enthält Anfang, Ende und die zugehörige Überschrift.
    ranges = []

    # None bedeutet: Es hat noch kein neuer Abschnitt begonnen.
    start_line = None
    heading = ""
    inside_code_block = False

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Drei Backticks öffnen oder schließen einen Codeblock.
        # Das gilt auch für beispielsweise ```mermaid oder ```bash.
        if stripped.startswith("```"):
            inside_code_block = not inside_code_block

        # Nur außerhalb eines Codeblocks gelten Leerzeilen und
        # Markdown-Überschriften als Abschnittsgrenzen.
        if not inside_code_block:
            # Erkennt ein bis sechs # mit anschließendem Leerraum.
            # group(1) enthält später den Text hinter den #.
            heading_match = re.match(r"^#{1,6}\s+(.+)$", stripped)

            if not stripped or heading_match:
                if start_line is not None:
                    # Die aktuelle Grenzzeile gehört nicht mehr
                    # zum bisherigen Abschnitt.
                    ranges.append(
                        (start_line, line_number - 1, heading)
                    )
                    start_line = None

                if heading_match:
                    # Diese Überschrift gilt für die folgenden Abschnitte.
                    heading = heading_match.group(1)

                continue

        # Die erste Inhaltszeile beginnt einen neuen Abschnitt.
        if start_line is None:
            start_line = line_number

    # Auch ohne abschließende Leerzeile müssen wir den letzten
    # Abschnitt am Dateiende übernehmen.
    if start_line is not None:
        ranges.append((start_line, len(lines), heading))

    chunks = []

    for start, end, section_heading in ranges:
        # Übernimm den Originaltext mit seinen ursprünglichen Zeilen.
        # Dateizeilen beginnen bei 1, Listenindizes bei 0.
        text = "\n".join(lines[start - 1 : end])

        # Überspringe Abschnitte, die nur aus Leerraum und
        # Trennzeichen bestehen, beispielsweise "---" oder "| --- |".
        if not text.strip(" \t\n|:-"):
            continue

        chunks.append(
            {
                "path": str(path),
                "heading": section_heading,
                "start_line": start,
                "end_line": end,
                "text": text,
            }
        )

    return chunks


def split_chunk_by_lines(chunk, count_tokens, max_tokens):
    """Teilt einen Abschnitt nach vollständigen Zeilen innerhalb des Limits."""
    lines = chunk["text"].split("\n")
    parts = []

    # buffer sammelt die Zeilen des gerade entstehenden Teils.
    buffer = []
    start_line = chunk["start_line"]

    for line_number, line in enumerate(lines, start=chunk["start_line"]):
        # Eine einzelne überlange Zeile können wir mit dieser Methode
        # nicht weiter teilen. Wir schneiden ihren Inhalt nicht ab.
        if count_tokens(line) > max_tokens:
            raise ValueError(
                f"{chunk['path']}, Zeile {line_number}: "
                f"Eine einzelne Zeile überschreitet "
                f"das Tokenlimit {max_tokens}."
            )

        # Prüfe, ob die nächste Zeile noch zum aktuellen Teil passt.
        candidate = "\n".join(buffer + [line])

        if buffer and count_tokens(candidate) > max_tokens:
            # Kopiere die Metadaten und passe Text und Zeilenbereich an.
            # Der ursprüngliche Abschnitt bleibt unverändert.
            part = chunk.copy()
            part["start_line"] = start_line
            part["end_line"] = line_number - 1
            part["text"] = "\n".join(buffer)
            parts.append(part)

            # Die aktuelle Zeile beginnt jetzt den nächsten Teil.
            buffer = []
            start_line = line_number

        buffer.append(line)

    # Übernimm die zuletzt gesammelten Zeilen.
    part = chunk.copy()
    part["start_line"] = start_line
    part["end_line"] = chunk["end_line"]
    part["text"] = "\n".join(buffer)
    parts.append(part)

    return parts