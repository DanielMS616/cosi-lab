"""Prüft, ob die RAG-Suche den erwarteten Beleg für W01 findet.

Das Skript durchsucht den Praxisbestand mit E5 und PostgreSQL.
Es gibt den Rang des erwarteten Absatzes unter den ersten drei
Treffern aus. Fehlt der Absatz, endet das Skript mit Exit-Code 1.

Starte es mit RAG_BESTAND=praxis. GPT und Gemini werden nicht aufgerufen.
"""


from rag_suche import suche_fuer_frage

FRAGE = "Nach wie vielen Betriebsstunden soll das Ansaugsieb am Prüfstand West kontrolliert werden?"
TOP_K = 3

# Ein Beleg besteht aus Dateipfad, Startzeile und Endzeile.
ERWARTETER_BELEG = ("examples/rag-praxis/wartungsanweisung-p17.md", 3, 5)


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


def main():
    print(f"W01: {FRAGE}")

    # Die Suche liefert Treffer und zwei Zeitwerte. Hier brauchen wir nur die Treffer.
    fundstellen, _, _ = suche_fuer_frage(FRAGE, top_k=TOP_K)
    rang = finde_belegrang(fundstellen, ERWARTETER_BELEG)

    datei, start, ende = ERWARTETER_BELEG
    belegtext = f"{datei}:{start}-{ende}"

    if rang is None:
        print(f"FEHLT: {belegtext} (in den ersten {TOP_K} Treffern)")
        return 1

    print(f"OK: Rang {rang} von {len(fundstellen)} · {belegtext}")
    return 0


if __name__ == "__main__":
    # Der Rückgabewert wird zum Exit-Code: 0 bedeutet Erfolg, 1 bedeutet Fehler.
    raise SystemExit(main())