"""Vergleicht Zitate in einer Modellantwort mit den übergebenen Fundstellen."""

import re


# Beispiel: examples/rag/fraese-f07.md:3-5
# [\w./-]+ erlaubt im Pfad Buchstaben, Zahlen, Unterstriche, Punkte,
# Schrägstriche und Bindestriche. Das + bedeutet „mindestens ein Zeichen“.
# \.md steht für die wörtliche Endung .md. Nach dem Doppelpunkt
# erwarten wir zwei Zeilennummern, getrennt durch einen Bindestrich.
# \b markiert das Ende der letzten Zahl, etwa vor einer Klammer.
ZITATMUSTER = re.compile(r"[\w./-]+\.md:[0-9]+-[0-9]+\b")


def pruefe_zitate(antwort, fundstellen):
    """Gibt erkannte und unbekannte Zitate in der Reihenfolge der Antwort zurück."""

    # Baue aus den Fundstellen dieselben Zeichenketten wie im Prompt.
    # Ein Set eignet sich hier, weil wir nur prüfen, ob ein Zitat darin steht.
    erlaubt = set()
    for fundstelle in fundstellen:
        datei = fundstelle["datei"]
        start = fundstelle["startzeile"]
        ende = fundstelle["endzeile"]
        erlaubt.add(f"{datei}:{start}-{ende}")

    erkannt = []
    unbekannt = []

    # findall liefert die Zitate in der Reihenfolge, in der sie vorkommen.
    for zitat in ZITATMUSTER.findall(antwort):
        # Überspringe Wiederholungen, damit jedes Zitat nur einmal auftaucht.
        if zitat in erkannt:
            continue
        erkannt.append(zitat)

        # Dateipfad und beide Zeilennummern müssen gemeinsam passen.
        # Zwei getrennte Bereiche dürfen nicht zu einem Zitat verschmelzen.
        if zitat not in erlaubt:
            unbekannt.append(zitat)

    return {"erkannt": erkannt, "unbekannt": unbekannt}