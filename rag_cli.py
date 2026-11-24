"""Terminalprogramm für die Dokusuche und optionale Modellantworten."""

import argparse

from rag_prompt import baue_prompt
from rag_embeddings import E5_MODELL
from rag_suche import suche_fuer_frage
from rag_ablauf import beantworte_und_speichere


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
            # Der Antwortablauf prüft und speichert. Die CLI zeigt das Ergebnis an.
            anbieter = "GPT" if args.gpt else "Gemini"
            ergebnis, zitatpruefung, lauf_id = beantworte_und_speichere(
                frage,
                prompt,
                sichtbare_treffer,
                anbieter=anbieter.lower(),
                top_k=args.top_k,
                suchmodell=E5_MODELL,
                e5_load_ms=e5_load_ms,
                retrieval_ms=retrieval_ms,
            )

            print(f"\n{anbieter}-Antwort:")
            print(ergebnis["text"])

            # Warne nur bei Zitaten, die nicht zu einer übergebenen Fundstelle passen.
            if zitatpruefung["unbekannt"]:
                print("\nZitatwarnung: Diese Fundstellen standen nicht im Prompt:")
                for zitat in zitatpruefung["unbekannt"]:
                    print(f"- {zitat}")

            # Nur der vorhandene GPT-Adapter liefert diese Statusfelder.
            if args.gpt:
                print(f"\nAPI-Status: {ergebnis['status']}")
                if ergebnis["incomplete_reason"]:
                    print(f"Grund: {ergebnis['incomplete_reason']}")

            print(f"RAG-Lauf gespeichert: ID {lauf_id}")


if __name__ == "__main__":
    main()
