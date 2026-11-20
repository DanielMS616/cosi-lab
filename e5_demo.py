import argparse
from pathlib import Path

from sentence_transformers import SentenceTransformer


def lese_absaetze(datei):
    """Liest die Absätze unserer Beispieldatei mit ihren Zeilennummern."""
    zeilen = datei.read_text(encoding="utf-8").splitlines()

    # Eine zusätzliche Leerzeile schließt auch den letzten Absatz ab.
    zeilen.append("")

    absaetze = []
    absatzzeilen = []
    startzeile = None

    for nummer, zeile in enumerate(zeilen, start=1):
        # Titelzeilen mit "# " und Leerzeilen gehören nicht zum Absatztext.
        if zeile.strip() and not zeile.startswith("# "):
            if not absatzzeilen:
                startzeile = nummer
            absatzzeilen.append(zeile)
        elif absatzzeilen:
            # Der Absatz endet eine Zeile vor dem Trenner.
            absaetze.append({
                "datei": datei.name,
                "startzeile": startzeile,
                "endzeile": nummer - 1,
                "text": "\n".join(absatzzeilen),
            })
            absatzzeilen = []

    return absaetze

""" Der Ablauf: Bei der ersten Textzeile merken wir uns den Anfang. 
Weitere Textzeilen kommen dazu. Sobald eine Leerzeile folgt, speichern wir den fertigen Absatz."""


def suche_e5(modell, frage, abschnitte):
    """Gibt die Absätze mit ihren Ähnlichkeitswerten sortiert zurück."""
    fragevektor = modell.encode(f"query: {frage}", normalize_embeddings=True)
    treffer = []

    for abschnitt in abschnitte:
        textvektor = modell.encode(
            f"passage: {abschnitt['text']}", normalize_embeddings=True
        )

        # Das Skalarprodukt der normierten Vektoren ist die Kosinusähnlichkeit.
        aehnlichkeit = float(fragevektor @ textvektor)

        # **abschnitt übernimmt Datei, Zeilen und Text in den neuen Treffer.
        treffer.append({**abschnitt, "wert": aehnlichkeit})

    return sorted(treffer, key=lambda eintrag: eintrag["wert"], reverse=True)


def main():
    # argparse liest die Frage aus dem Terminal und speichert sie in args.frage.
    parser = argparse.ArgumentParser(
        description="Durchsucht Beispielabsätze mit E5."
    )
    parser.add_argument("frage", help="Suchfrage in Anführungszeichen")
    # Ohne --show-text ist args.show_text False, mit dem Schalter True.
    parser.add_argument(
        "--show-text",
        action="store_true",
        help="Zeigt den Originaltext des besten Treffers.",
    )
    # Lies die gewünschte Anzahl als ganze Zahl ein.
    parser.add_argument(
        "--top-k",
        type=int,
        metavar="ANZAHL",
        help="Zeigt höchstens ANZAHL Treffer. Ohne Schalter erscheinen alle.",
    )
    args = parser.parse_args()

    # Entferne Leerzeichen am Anfang und Ende. Brich bei einer leeren Frage
    # ab, bevor das E5-Modell geladen wird.
    frage = args.frage.strip()
    if not frage:
        parser.error("Die Frage darf nicht leer sein.")

    # Ohne --top-k ist args.top_k None. Eine angegebene Zahl muss positiv sein.
    if args.top_k is not None and args.top_k < 1:
        parser.error("--top-k muss mindestens 1 sein.")

    ordner = Path(__file__).parent / "examples" / "rag"

    # Jede Datei liefert ihre Absätze für dieselbe Suchliste.
    abschnitte = []
    for dateiname in (
            "nachtflug-rack.md",
            "fraese-f07.md",
            "masspruefung-h12.md",
    ):
        abschnitte.extend(lese_absaetze(ordner / dateiname))

    modell = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
    treffer = suche_e5(modell, frage, abschnitte)

    print(f"Frage: {frage}")
    print(f"Geprüfte Absätze: {len(abschnitte)}")

    # Nimm nur die ersten k Treffer für die Anzeige. Bei None nimm alle.
    sichtbare_treffer = treffer[:args.top_k]
    for rang, eintrag in enumerate(sichtbare_treffer, start=1):
        fundstelle = f"{eintrag['datei']}:{eintrag['startzeile']}-{eintrag['endzeile']}"
        print(f"{rang}. {fundstelle}  {eintrag['wert']:.3f}")

    # Prüfe, ob der Schalter gesetzt ist und mindestens ein Treffer vorliegt.
    if args.show_text and treffer:
        bester_treffer = treffer[0]  # Die Liste ist bereits nach Rang sortiert.
        print("\nOriginaltext zu Platz 1:")
        print(bester_treffer["text"])


if __name__ == "__main__":
    main()