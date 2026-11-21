"""Terminalprogramm für die Dokusuche und optionale Modellantworten."""

import argparse

from time import perf_counter
from datetime import datetime, timezone

from rag_prompt import baue_prompt
from rag_zitate import pruefe_zitate
from rag_embeddings import E5_MODELL
from rag_suche import suche_fuer_frage

def main():
    parser = argparse.ArgumentParser(description="Durchsucht Beispielabsätze mit E5.")
    parser.add_argument("frage", help="Suchfrage in Anführungszeichen")
    # Ohne Schalter bleibt args.show_text False, mit Schalter wird es True.
    parser.add_argument(
        "--show-text",
        action="store_true",
        help="Zeigt den Originaltext des besten Treffers.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        metavar="ANZAHL",
        help="Zeigt höchstens ANZAHL Treffer. Ohne Schalter erscheinen alle.",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="Zeigt den Prompt mit den ausgewählten Fundstellen.",
    )
    # Pro Aufruf kann höchstens ein Antwortmodell gewählt werden.
    modellschalter = parser.add_mutually_exclusive_group()
    modellschalter.add_argument(
        "--gpt",
        action="store_true",
        help="Sendet den Prompt an GPT und zeigt die Antwort.",
    )
    modellschalter.add_argument(
        "--gemini",
        action="store_true",
        help="Sendet den Prompt an Gemini und zeigt die Antwort.",
    )
    args = parser.parse_args()

    frage = args.frage.strip()
    if not frage:
        parser.error("Die Frage darf nicht leer sein.")

    # Ohne --top-k ist der Wert None; nur angegebene Zahlen müssen wir prüfen.
    if args.top_k is not None and args.top_k < 1:
        parser.error("--top-k muss mindestens 1 sein.")

    # Die Suche liefert Daten. Die CLI entscheidet, was sie davon ausgibt.
    sichtbare_treffer, e5_load_ms, retrieval_ms = suche_fuer_frage(
        frage, args.top_k
    )
    if not sichtbare_treffer:
        print("Keine Absätze in PostgreSQL gefunden. Führe zuerst rag_import.py aus.")
        return

    # Nur dieser Teil formatiert das Ergebnis für das Terminal.
    print(f"Frage: {frage}")
    print(f"Treffer aus PostgreSQL: {len(sichtbare_treffer)}")
    for rang, eintrag in enumerate(sichtbare_treffer, start=1):
        fundstelle = f"{eintrag['datei']}:{eintrag['startzeile']}-{eintrag['endzeile']}"
        print(f"{rang}. {fundstelle}  {eintrag['wert']:.3f}")

    if args.show_text:
        bester_treffer = sichtbare_treffer[0]  # PostgreSQL hat schon sortiert.
        print("\nOriginaltext zu Platz 1:")
        print(bester_treffer["text"])

    # Baue den Prompt einmal für die Vorschau und das gewählte Modell.
    mit_antwort = args.gpt or args.gemini
    if args.show_prompt or mit_antwort:
        prompt = baue_prompt(frage, sichtbare_treffer)

        if args.show_prompt:
            print("\nPromptvorschau:")
            print(prompt)

        if mit_antwort:
            from rag_run_storage import RUN_DATABASE, save_rag_run

            # Importiere nur den Adapter für das gewählte Modell.
            if args.gpt:
                from model_gpt import GPT_MODEL, generate_gpt_report

                antwort_funktion = generate_gpt_report
                anbieter = "GPT"
                antwortmodell = GPT_MODEL
            else:
                from model_gemini import GEMINI_MODEL, generate_gemini_report

                antwort_funktion = generate_gemini_report
                anbieter = "Gemini"
                antwortmodell = GEMINI_MODEL

            # Prompt und Ausgabelimit sind für beide Anbieter gleich.
            token_limit = 240
            requested_at_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            api_start = perf_counter()
            ergebnis = antwort_funktion(prompt, max_output_tokens=token_limit)
            client_duration_ms = round((perf_counter() - api_start) * 1_000)
            print(f"\n{anbieter}-Antwort:")
            print(ergebnis["text"])

            # Vergleiche die Zitate in der Antwort mit genau den Absätzen,
            # die das Modell im Prompt gesehen hat.
            zitatpruefung = pruefe_zitate(ergebnis["text"], sichtbare_treffer)
            unbekannte_zitate = zitatpruefung["unbekannt"]

            # Python betritt diesen Block nur, wenn die Liste Einträge enthält.
            # Bei einer Antwort ohne Zitat bleibt die Liste ebenfalls leer.
            if unbekannte_zitate:
                print("\nZitatwarnung: Diese Fundstellen standen nicht im Prompt:")
                for zitat in unbekannte_zitate:
                    print(f"- {zitat}")

            # Nur der vorhandene GPT-Adapter liefert diese Statusfelder.
            if args.gpt:
                print(f"\nAPI-Status: {ergebnis['status']}")
                if ergebnis["incomplete_reason"]:
                    print(f"Grund: {ergebnis['incomplete_reason']}")

            # Speichere dieselbe Frage, denselben Prompt und dieselben Quellen,
            # die verwendet wurden. Nicht gemeldete Werte bleiben in SQLite NULL.
            lauf = {
                "requested_at_utc": requested_at_utc,
                "question": frage,
                "top_k": args.top_k,
                "retrieval_model": E5_MODELL,
                "provider": anbieter.lower(),
                "model": antwortmodell,
                "max_output_tokens": token_limit,
                "prompt": prompt,
                "response_text": ergebnis["text"],
                "input_tokens": ergebnis.get("input_tokens"),
                "output_tokens": ergebnis.get("output_tokens"),
                "e5_load_ms": e5_load_ms,
                "retrieval_ms": retrieval_ms,
                "client_duration_ms": client_duration_ms,
                "provider_duration_ms": ergebnis.get("processing_ms"),
                "api_status": ergebnis.get("status"),
                "incomplete_reason": ergebnis.get("incomplete_reason"),
            }
            lauf_id = save_rag_run(RUN_DATABASE, lauf, sichtbare_treffer)
            print(f"RAG-Lauf gespeichert: ID {lauf_id}")


if __name__ == "__main__":
    main()
