from pathlib import Path

from sentence_transformers import SentenceTransformer


def lese_ersten_absatz(datei):
    """Liest bei unseren Beispieldateien den ersten Absatz nach dem Titel."""
    inhalt = datei.read_text(encoding="utf-8")

    # Die Leerzeile trennt den Titel vom ersten Absatz.
    # Daher ist der Titel an Position 0 und der Absatz an Position 1.
    return inhalt.split("\n\n", maxsplit=2)[1]


def suche_e5(modell, frage, abschnitte):
    """Gibt die Dateinamen und Ähnlichkeitswerte in bester Reihenfolge zurück."""
    # E5 unterscheidet Fragen (query) und Textabschnitte (passage).
    fragevektor = modell.encode(f"query: {frage}", normalize_embeddings=True)
    treffer = []

    for dateiname, text in abschnitte:
        textvektor = modell.encode(f"passage: {text}", normalize_embeddings=True)

        # Bei Vektoren der Länge 1 ergibt das Skalarprodukt (@) die
        # Kosinusähnlichkeit. Je höher der Wert, desto ähnlicher die Richtung.
        aehnlichkeit = float(fragevektor @ textvektor)
        treffer.append({"datei": dateiname, "wert": aehnlichkeit})

    # Der größte Wert soll auf Platz 1 stehen.
    return sorted(treffer, key=lambda eintrag: eintrag["wert"], reverse=True)


def main():
    ordner = Path(__file__).parent / "examples" / "rag"
    frage = "Zählt genau 60 °C bei der Fräse schon als Überschreitung?"

    # Das Rack steht bewusst zuerst in der Liste: E5 soll selbst sortieren.
    abschnitte = []
    for dateiname in ("nachtflug-rack.md", "fraese-f07.md"):
        text = lese_ersten_absatz(ordner / dateiname)
        abschnitte.append((dateiname, text))

    modell = SentenceTransformer("intfloat/multilingual-e5-small", device="cpu")
    treffer = suche_e5(modell, frage, abschnitte)

    # Nur main() formatiert das Ergebnis für das Terminal.
    print(f"Frage: {frage}")
    for rang, eintrag in enumerate(treffer, start=1):
        print(f"{rang}. {eintrag['datei']}: {eintrag['wert']:.3f}")


if __name__ == "__main__":
    main()