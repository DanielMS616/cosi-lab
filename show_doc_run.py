import argparse
import sqlite3

from doc_storage import load_doc_run


def main():
    """Zeigt einen gespeicherten Dokulauf anhand seiner ID an."""
    parser = argparse.ArgumentParser(description="Zeigt einen gespeicherten Dokulauf.")
    parser.add_argument("run_id", type=int, help="ID aus der Tabelle doc_runs")
    parser.add_argument(
        "--database",
        default="data/model_runs.sqlite3",
        help="Pfad zur SQLite-Datei (Standard: %(default)s)",
    )
    args = parser.parse_args()

    # Ein Datenbankfehler ist etwas anderes als eine ID, die nicht existiert.
    try:
        run = load_doc_run(args.database, args.run_id)
    except sqlite3.Error as error:
        parser.exit(1, f"Datenbank konnte nicht gelesen werden: {error}\n")

    if run is None:
        parser.exit(1, f"Kein Dokulauf mit ID {args.run_id} gefunden.\n")

    print(f"Dokulauf {run['id']} · {run['model']}")
    print(f"Aufrufzeitpunkt (UTC): {run['requested_at_utc']}")
    print(f"Frage: {run['question']}")
    print(f"API-Status: {run['api_status'] or 'nicht erfasst'}")

    if run["incomplete_reason"] is not None:
        print(f"Grund für unvollständige Antwort: {run['incomplete_reason']}")

    print("\nGesendeter Prompt:")
    print(run["prompt"])

    # Die Ausschnitte kommen aus SQLite, so wie sie beim Aufruf vorlagen.
    print("\nGespeicherte Fundstellen:")
    for number, source in enumerate(run["sources"], start=1):
        location = f"{source['path']}:{source['start_line']}-{source['end_line']}"
        print(f"Fundstelle {number}: {location}")
        print(source["text"])

    print("\nAntwort:")
    print(run["response_text"])

    print("\nZitatprüfung zum Zeitpunkt des Aufrufs:")
    cited = run["citations"]["cited"]
    unknown = run["citations"]["unknown"]
    print("Erkannte Fundstellen:", ", ".join(cited) if cited else "keine")
    print("Unbekannte Fundstellen:", ", ".join(unknown) if unknown else "keine")


if __name__ == "__main__":
    main()