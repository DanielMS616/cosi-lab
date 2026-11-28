"""Prüft die RAG-Suche für die vier Praxisfälle W01 bis W05.

Das Skript sucht einmal pro Frage und zeigt den Rang jedes erwarteten
Belegs unter den ersten Treffern; die Anzahl lässt sich mit --top-k
einstellen (Standard: 3). Fehlt mindestens ein Beleg,
endet der Aufruf mit Exit-Code 1.

Mit RAG_BESTAND=praxis starten. GPT und Gemini werden nicht aufgerufen.
"""


import argparse

from rag_suche import suche_fuer_frage

TOP_K = 3

# Jeder Prüffall enthält seine Frage und eine Liste erwarteter Fundstellen.
# Eine Fundstelle besteht aus Dateipfad, Startzeile und Endzeile.
PRUEFFAELLE = [
    {
        "kennung": "W01",
        "frage": (
            "Nach wie vielen Betriebsstunden soll das Ansaugsieb "
            "am Prüfstand West kontrolliert werden?"
        ),
        "belege": [("examples/rag-praxis/wartungsanweisung-p17.md", 3, 5)],
    },
    {
        "kennung": "W02",
        "frage": (
            "Woran lag der geringe Durchfluss bei P-17 am 18. November, "
            "und wie hoch war er nach der Reinigung?"
        ),
        "belege": [("examples/rag-praxis/stoerungsprotokoll-p17.md", 3, 5)],
    },
    {
        "kennung": "W03",
        "frage": (
            "Welche Teilenummer hat der Siebeinsatz für P-17, "
            "und nach wie vielen Betriebsstunden ist die Siebkontrolle fällig?"
        ),
        "belege": [
            ("examples/rag-praxis/teileliste-p17.md", 3, 4),
            ("examples/rag-praxis/wartungsanweisung-p17.md", 3, 5),
        ],
    },
    {
        "kennung": "W04",
        "frage": "Was kostet der Siebeinsatz für P-17, und welche Teilenummer hat er?",
        # Hier prüfen wir nur den Beleg für die Teilenummer.
        # Ob das Modell den fehlenden Preis richtig behandelt, ist ein eigener Test.
        "belege": [("examples/rag-praxis/teileliste-p17.md", 3, 4)],
    },
    {
        "kennung": "W05",
        "frage": (
            "In welchem Fach liegt der Siebeinsatz S-271, "
            "und für welche Pumpe ist er vorgesehen?"
        ),
        # Derselbe Absatz belegt das Lagerfach und die Zuordnung zur Pumpe.
        "belege": [("examples/rag-praxis/wartungsanweisung-p71.md", 11, 13)],
    },
]


def finde_belegrang(fundstellen, erwarteter_beleg):
    """Gibt den Rang des Belegs zurück oder None, falls er fehlt."""
    # Die Suche liefert die Treffer bereits sortiert. Wir zählen ab 1.
    for rang, fundstelle in enumerate(fundstellen, start=1):
        # Der richtige Dateiname allein reicht nicht: Auch die Zeilen müssen stimmen.
        adresse = (
            fundstelle["datei"],
            fundstelle["startzeile"],
            fundstelle["endzeile"],
        )
        if adresse == erwarteter_beleg:
            return rang

    return None


def pruefe_fall(fall, top_k, markdown=False):
    """Sucht einmal und gibt die Belegprüfung als Text oder Tabellenzeile aus."""
    if not markdown:
        print(f"\n{fall['kennung']}: {fall['frage']}")

    fundstellen, _, _ = suche_fuer_frage(fall["frage"], top_k=top_k)
    alle_belege_gefunden = True
    befunde = []

    for beleg in fall["belege"]:
        datei, start, ende = beleg
        belegtext = f"{datei}:{start}-{ende}"
        rang = finde_belegrang(fundstellen, beleg)

        if rang is None:
            meldung = f"FEHLT: {belegtext} (in den ersten {top_k} Treffern)"
            alle_belege_gefunden = False
        else:
            meldung = f"OK: Rang {rang} von {len(fundstellen)} · {belegtext}"

        # In der Tabelle kommen alle Belege des Falls in dieselbe Zelle.
        if markdown:
            befunde.append(meldung)
        else:
            print(meldung)

    if markdown:
        ergebnis = "bestanden" if alle_belege_gefunden else "nicht bestanden"
        print(f"| {fall['kennung']} | {'; '.join(befunde)} | {ergebnis} |")

    return alle_belege_gefunden


def main():
    parser = argparse.ArgumentParser(description="Prüft die RAG-Suche für W01 bis W05.")
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        metavar="ANZAHL",
        help="Höchstens so viele Treffer je Frage (Standard: %(default)s).",
    )
    # store_true bedeutet: Ohne Schalter ist args.markdown False.
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Gibt die Ergebnisse als Markdown-Tabelle fürs Prüfprotokoll aus.",
    )
    args = parser.parse_args()

    # Eine ungültige Trefferzahl soll gar keine Suche starten.
    if args.top_k < 1:
        parser.error("--top-k muss mindestens 1 sein.")

    if args.markdown:
        print(f"\n### Suchcheck mit Top-k {args.top_k}\n")
        print("| Fall | Erwartete Belege und Trefferpositionen | Ergebnis |")
        print("| --- | --- | --- |")

    bestanden = 0
    for fall in PRUEFFAELLE:
        if pruefe_fall(fall, args.top_k, markdown=args.markdown):
            bestanden += 1

    zusammenfassung = f"{bestanden} von {len(PRUEFFAELLE)} Suchchecks bestanden."
    if args.markdown:
        print(f"| **Gesamt** | | **{zusammenfassung}** |")
    else:
        print(f"\nTop-k {args.top_k}: {zusammenfassung}")

    # Das Ausgabeformat ändert nichts daran, ob der Suchcheck bestanden ist.
    return 0 if bestanden == len(PRUEFFAELLE) else 1


if __name__ == "__main__":
    # Der Rückgabewert wird zum Exit-Code: 0 bedeutet Erfolg, 1 bedeutet Fehler.
    raise SystemExit(main())