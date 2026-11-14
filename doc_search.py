import re
import argparse

from pathlib import Path
from doc_prompt import build_doc_prompt, build_multi_doc_prompt, check_citations


# Diese beiden Dateien durchsucht --project-docs vom Projektordner aus.
PROJECT_DOCS = (
    "docs/aufbau-hardware.md",
    "docs/aufbau-fernzugriff.md",
)


def question_to_terms(question):
    """Gewinnt Suchwörter aus einer Frage."""
    # Diese Wörter helfen bei unserer Dokusuche meist nicht weiter.
    stop_words = {
        "wie", "was", "ist", "funktioniert", "der", "die", "das",
        "ein", "eine", "im", "in", "mit", "und", "auf",
        # Der Projektname steht in mehreren Dokumenten. Er soll allein
        # keinen Treffer auslösen, wenn das eigentliche Thema fehlt.
        "cosi", "lab",
    }

    # findall() sammelt die Wörter in ihrer Reihenfolge. Bindestrich
    # und Fragezeichen trennen Wörter: Aus WireGuard-Tunnel werden zwei.
    words = re.findall(r"\w+", question.casefold())

    # In der Hardware-Doku steht „CPU“. Suche auch danach,
    # wenn in der Frage „Prozessor“ steht.
    aliases = {"prozessor": "cpu"}

    return [aliases.get(word, word) for word in words if word not in stop_words]


def find_excerpt(path, phrase):
    """Gibt den ersten Treffer mit bis zu zwei Zeilen davor zurück."""
    # strip() entfernt Leerzeichen am Rand. casefold() macht den
    # Vergleich unabhängig von Groß- und Kleinschreibung.
    needle = phrase.strip().casefold()

    # Ein leerer String wäre in jeder Zeile enthalten. Deshalb brechen
    # wir bei einer leeren Suchphrase ab, bevor wir die Datei lesen.
    if not needle:
        return None

    file_path = Path(path)                        # Pfad zur Datei
    text = file_path.read_text(encoding="utf-8")  # Dateiinhalt als ein String
    lines = text.splitlines()                     # Ein String pro Zeile

    # enumerate() liefert pro Durchlauf die Zeilennummer und den Zeilentext.
    # start=1 nummeriert wie in einem Editor: Die erste Zeile hat Nummer 1.
    for line_number, line in enumerate(lines, start=1):
        # Hier findet die Suche statt: Kommt die gesamte Phrase
        # zusammenhängend in dieser Zeile vor?
        if needle in line.casefold():
            # Nimm bis zu zwei Zeilen vor dem Treffer als Kontext mit.
            # max() verhindert, dass der Ausschnitt vor Zeile 1 beginnt.
            start_line = max(1, line_number - 2)

            # Listenindizes beginnen bei 0, und das rechte Ende ist
            # ausgeschlossen. Beispiel: lines[9:12] ergibt Zeilen 10–12.
            excerpt = lines[start_line - 1 : line_number]

            # join() setzt die Zeilen wieder zu einem Text zusammen.
            # return beendet die Funktion beim ersten Treffer.
            return {
                "path": str(path),
                "start_line": start_line,
                "end_line": line_number,
                "text": "\n".join(excerpt),
            }

    # Erst wenn alle Zeilen geprüft sind, steht fest: Es gab keinen Treffer.
    return None


def find_best_excerpt(path, question):
    """Gibt den Ausschnitt mit den meisten passenden Suchwörtern zurück."""
    # Ein Set zählt jedes Suchwort nur einmal, auch wenn es in der Frage
    # mehrfach vorkommt.
    terms = set(question_to_terms(question))
    if not terms:
        return None

    lines = Path(path).read_text(encoding="utf-8").splitlines()
    best_hit = None
    best_score = 0

    # Gehe die Datei von oben nach unten durch. end_line ist die Nummer
    # der aktuellen Zeile. Wir betrachten sie und bis zu zwei Zeilen davor.
    for end_line in range(1, len(lines) + 1):
        # Bei Zeile 12 beginnen wir bei 10. Bei Zeile 1 oder 2 sorgt max()
        # dafür, dass wir bei Zeile 1 anfangen.
        start_line = max(1, end_line - 2)

        # Dateizeile 10 hat Listenindex 9. Für die Zeilen 10 bis 12
        # nehmen wir lines[9:12]: Das enthält die Indizes 9, 10 und 11.
        text = "\n".join(lines[start_line - 1 : end_line])

        # Sammle die Wörter des gesamten Ausschnitts. & behält nur
        # Wörter, die auch in der Frage vorkommen.
        excerpt_words = set(re.findall(r"\w+", text.casefold()))
        matched_terms = terms & excerpt_words
        score = len(matched_terms)

        # Speichere den Ausschnitt nur, wenn er mehr Suchwörter trifft
        # als der bisher beste. Bei Gleichstand bleibt der frühere Treffer.
        if score > best_score:
            best_score = score
            best_hit = {
                "path": str(path),
                "start_line": start_line,
                "end_line": end_line,
                "text": text,
                "matched_terms": sorted(matched_terms),
            }

    # Wenn kein Ausschnitt auch nur ein Suchwort enthielt, bleibt es bei None.
    return best_hit


def find_best_excerpt_in_files(paths, question):
    """Wählt aus mehreren Dateien den Ausschnitt mit den meisten Suchtreffern."""
    best_hit = None
    best_score = 0

    for path in paths:
        # Nutze die vorhandene Suche, um den besten Ausschnitt dieser Datei zu finden.
        hit = find_best_excerpt(path, question)
        if hit is None:
            continue

        # Vergleiche, wie viele unterschiedliche Suchwörter gefunden wurden.
        # Bei Gleichstand bleibt der Treffer aus der zuerst geprüften Datei.
        score = len(hit["matched_terms"])
        if score > best_score:
            best_hit = hit
            best_score = score

    return best_hit


def find_top_excerpts_in_files(paths, question):
    """Gibt bis zu zwei Fundstellen zurück, die am besten zur Frage passen."""
    hits = []

    for path in paths:
        # Pro Datei nehmen wir ihren besten Ausschnitt mit.
        hit = find_best_excerpt(path, question)
        if hit is not None:
            hits.append(hit)

    # Die Anzahl passender Suchwörter entscheidet über die Reihenfolge.
    # reverse=True sortiert absteigend: Der Treffer mit den meisten steht vorn.
    # Bei Gleichstand bleibt die Reihenfolge der Dateien erhalten.
    hits.sort(key=lambda hit: len(hit["matched_terms"]), reverse=True)

    # Nimm höchstens zwei Treffer. Bei einem Treffer bleibt es bei einem,
    # und ohne Treffer kommt eine leere Liste zurück.
    return hits[:2]


def main():
    """Nimmt die Terminalargumente entgegen und zeigt das Suchergebnis an."""
    parser = argparse.ArgumentParser(description="Sucht eine Phrase in einer Datei.")

    # Die Reihenfolge im Terminal ist: erst der Dateipfad, dann die Suchphrase.
    parser.add_argument("path", nargs="?", help="Pfad zur Datei")
    parser.add_argument(
        "--project-docs",
        action="store_true",
        help="Durchsucht die festgelegten Projektdokumente.",
    )
    parser.add_argument("phrase", help="Suchphrase, z. B. 'ssh im tunnel'")
    parser.add_argument(
        "--question",
        action="store_true",
        help="Sucht den besten Ausschnitt anhand der Wörter in einer Frage.",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Zeigt den Modellprompt für eine Frage an.",
    )
    parser.add_argument(
        "--gpt",
        action="store_true",
        help="Sendet die Frage und die gefundene Textstelle an GPT.",
    )
    parser.add_argument(
        "--also-search",
        action="append",
        default=[],
        metavar="DATEI",
        help="Durchsucht eine weitere Datei. Kann mehrfach angegeben werden.",
    )
    parser.add_argument(
        "--multi-source",
        action="store_true",
        help="Zeigt bis zu zwei Fundstellen für eine Frage.",
    )
    args = parser.parse_args()

    # Die Projektdoku wird immer als Fragensuche ausgewertet.
    use_question_search = args.question or args.project_docs

    if args.multi_source and not use_question_search:
        parser.error("--multi-source setzt --question oder --project-docs voraus.")
    if args.project_docs and (args.path is not None or args.also_search):
        parser.error("--project-docs wird ohne Dateipfad und --also-search verwendet.")
    if args.path is None and not args.project_docs:
        parser.error("Gib einen Dateipfad oder --project-docs an.")
    if (args.show_prompt or args.gpt or args.also_search) and not use_question_search:
        parser.error("--show-prompt, --gpt und --also-search setzen --question voraus.")

    if use_question_search:
        paths = PROJECT_DOCS if args.project_docs else [args.path] + args.also_search
        hits = find_top_excerpts_in_files(paths, args.phrase)

        # Ohne den neuen Schalter verwende ich nur den besten Treffer.
        if not args.multi_source:
            hits = hits[:1]
    else:
        hit = find_excerpt(args.path, args.phrase)
        hits = [hit] if hit is not None else []

    if not hits:
        print("Keine passende Fundstelle gefunden.")
        return

    if args.show_prompt or args.gpt:
        # Vorschau und Modellaufruf verwenden denselben Prompt.
        if len(hits) == 1:
            prompt = build_doc_prompt(args.phrase, hits[0])
        else:
            prompt = build_multi_doc_prompt(args.phrase, hits)

        if args.show_prompt:
            print(prompt)

        if args.gpt:
            # Lade das API-Modul erst, wenn wirklich eine Anfrage ansteht.
            from model_gpt import generate_gpt_report

            # Dokufragen brauchen Platz für Antworten mit mehreren Quellenangaben.
            result = generate_gpt_report(prompt, max_output_tokens=240)
            print("\nGPT-Antwort:")
            print(result["text"])

            print(f"\nAPI-Status: {result['status']}")
            if result["incomplete_reason"] is not None:
                print(f"Grund für unvollständige Antwort: {result['incomplete_reason']}")

            # Vergleiche die Zitate in der Antwort mit denselben Treffern,
            # aus denen wir den Prompt gebaut haben.
            citations = check_citations(result["text"], hits)

            if citations["unknown"]:
                print("Fundstellen, die nicht im Prompt standen:")
                for source in citations["unknown"]:
                    print(f"- {source}")
            elif not citations["cited"]:
                print("Keine Fundstelle in der Antwort erkannt.")
            else:
                print("Alle erkannten Fundstellen standen im Prompt.")

        return

    for hit in hits:
        print(f"{hit['path']}:{hit['start_line']}-{hit['end_line']}")
        print(hit["text"])


# Beim direkten Start läuft main(). Beim Import von find_excerpt()
# bleibt die Funktion verfügbar, ohne Terminalargumente einzulesen.
if __name__ == "__main__":
    main()