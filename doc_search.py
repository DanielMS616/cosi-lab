import re
import argparse

from pathlib import Path
from doc_prompt import build_doc_prompt


def question_to_terms(question):
    """Gewinnt Suchwörter aus einer Frage."""
    # Diese Wörter helfen bei unserer Dokusuche meist nicht weiter.
    stop_words = {
        "wie", "was", "ist", "funktioniert", "der", "die", "das",
        "ein", "eine", "im", "in", "mit", "und", "auf",
    }

    # findall() sammelt die Wörter in ihrer Reihenfolge. Bindestrich
    # und Fragezeichen trennen Wörter: Aus WireGuard-Tunnel werden zwei.
    words = re.findall(r"\w+", question.casefold())

    # Übernimm nur Wörter, die nicht in der Ausschlussliste stehen.
    return [word for word in words if word not in stop_words]


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


def main():
    """Nimmt die Terminalargumente entgegen und zeigt das Suchergebnis an."""
    parser = argparse.ArgumentParser(description="Sucht eine Phrase in einer Datei.")

    # Die Reihenfolge im Terminal ist: erst der Dateipfad, dann die Suchphrase.
    parser.add_argument("path", help="Pfad zur Datei")
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
    args = parser.parse_args()

    # Eine Promptvorschau braucht eine Frage als Eingabe.
    if args.show_prompt and not args.question:
        parser.error("--show-prompt setzt --question voraus.")

    # Derselbe Suchtext wird je nach Schalter unterschiedlich ausgewertet.
    if args.question:
        hit = find_best_excerpt(args.path, args.phrase)
    else:
        hit = find_excerpt(args.path, args.phrase)

    # Bei None gibt es kein Dictionary. Beende main(), bevor wir auf
    # Felder wie hit["path"] zugreifen.
    if hit is None:
        print("Keine passende Fundstelle gefunden.")
        return

    if args.show_prompt:
        print(build_doc_prompt(args.phrase, hit))
        return

    print(f"{hit['path']}:{hit['start_line']}-{hit['end_line']}")
    print(hit["text"])


# Beim direkten Start läuft main(). Beim Import von find_excerpt()
# bleibt die Funktion verfügbar, ohne Terminalargumente einzulesen.
if __name__ == "__main__":
    main()