"""Zeigt einen gespeicherten RAG-Lauf aus SQLite an."""

import argparse
import sqlite3
from json import JSONDecodeError

from rag_zitate import pruefe_zitate
from rag_run_storage import RUN_DATABASE, load_rag_run


def zeige_lauf(lauf):
    """Gibt ausschließlich Daten aus dem gespeicherten Lauf aus."""
    print(f"RAG-Lauf {lauf['id']} · {lauf['model']}")
    print(f"Frage: {lauf['question']}")
    print(f"Anbieter: {lauf['provider']}")
    print(f"Aufrufzeitpunkt (UTC): {lauf['requested_at_utc']}")
    print(f"Suchmodell: {lauf['retrieval_model']}")
    top_k = "alle" if lauf["top_k"] is None else lauf["top_k"]
    print(f"Top-k: {top_k}")

    # Nur None bedeutet „nicht erfasst“. Der Messwert 0 bleibt sichtbar.
    for feld, beschriftung, einheit in (
        ("e5_load_ms", "E5 laden", " ms"),
        ("retrieval_ms", "Suche (Fragevektor und PostgreSQL)", " ms"),
        ("client_duration_ms", "Modellaufruf, lokal gemessen", " ms"),
        ("provider_duration_ms", "Verarbeitungszeit laut Anbieter", " ms"),
        ("input_tokens", "Eingabetoken", ""),
        ("output_tokens", "Ausgabetoken", ""),
        ("max_output_tokens", "Limit für Ausgabetoken", ""),
        ("api_status", "API-Status", ""),
    ):
        wert = lauf[feld]
        anzeige = "nicht erfasst" if wert is None else f"{wert}{einheit}"
        print(f"{beschriftung}: {anzeige}")
    if lauf["incomplete_reason"]:
        print(f"Grund für unvollständige Antwort: {lauf['incomplete_reason']}")

    print("\nAntwort:")
    print(lauf["response_text"])

    # SQLite liefert die gespeicherte Antwort und die Fundstellen von damals.
    # Damit prüfen wir genau den Stand, den das Modell bei diesem Lauf sah.
    zitatpruefung = pruefe_zitate(lauf["response_text"], lauf["sources"])
    unbekannte_zitate = zitatpruefung["unbekannt"]

    # Die Warnung wird nur für die Anzeige berechnet.
    # Der gespeicherte Lauf selbst bleibt unverändert.
    if unbekannte_zitate:
        print("\nZitatwarnung: Diese Fundstellen standen nicht im Prompt:")
        for zitat in unbekannte_zitate:
            print(f"- {zitat}")

    print("\nGespeicherte Fundstellen:")
    for rang, quelle in enumerate(lauf["sources"], start=1):
        fundstelle = f"{quelle['datei']}:{quelle['startzeile']}-{quelle['endzeile']}"
        print(f"{rang}. {fundstelle}  {quelle['wert']:.3f}")
        print(quelle["text"])

    print("\nGesendeter Prompt:")
    print(lauf["prompt"])


def main():
    parser = argparse.ArgumentParser(description="Zeigt einen gespeicherten RAG-Lauf an.")
    parser.add_argument("run_id", type=int, help="ID des RAG-Laufs")
    parser.add_argument("--database", default=RUN_DATABASE, help="Pfad zur SQLite-Datei")
    args = parser.parse_args()
    if args.run_id < 1:
        parser.error("Die Lauf-ID muss mindestens 1 sein.")

    try:
        lauf = load_rag_run(args.database, args.run_id)
    except (sqlite3.Error, JSONDecodeError) as error:
        parser.exit(1, f"Lauf konnte nicht gelesen werden: {error}\n")
    if lauf is None:
        parser.exit(1, f"Kein RAG-Lauf mit ID {args.run_id} gefunden.\n")

    zeige_lauf(lauf)


if __name__ == "__main__":
    main()
