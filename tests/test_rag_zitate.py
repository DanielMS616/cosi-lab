import unittest

from rag_zitate import pruefe_zitate


RACK = "examples/rag/nachtflug-rack.md"
FRAESE = "examples/rag/fraese-f07.md"


def fundstelle(datei, start, ende):
    """Baut eine Fundstelle im Format, das pruefe_zitate() erwartet."""
    return {"datei": datei, "startzeile": start, "endzeile": ende}


# Beide P06-Tests verwenden dieselben Absätze aus dem Prompt.
P06_FUNDSTELLEN = [
    fundstelle(RACK, 9, 10),
    fundstelle(FRAESE, 7, 8),
    fundstelle(RACK, 6, 7),
]


class ZitatpruefungTests(unittest.TestCase):
    def test_p04_erkennt_beide_exakten_zitate(self):
        fundstellen = [fundstelle(FRAESE, 3, 5), fundstelle(RACK, 3, 4)]
        antwort = (
            f"Die gelbe Anzeige am Rack leuchtet ({RACK}:3-4). "
            f"An der Fräse zählen 60 °C nicht als Überschreitung (`{FRAESE}:3-5`)."
        )

        # Die Zitatliste folgt der Reihenfolge in der Antwort, nicht im Prompt.
        self.assertEqual(
            pruefe_zitate(antwort, fundstellen),
            {"erkannt": [f"{RACK}:3-4", f"{FRAESE}:3-5"], "unbekannt": []},
        )

    def test_p06_antwort_ohne_zitat_liefert_leere_listen(self):
        antwort = "Nicht belegt: Öffnungszeit am Sonntag."

        # Auch wenn der Prompt Absätze enthält, muss die Antwort keinen zitieren.
        self.assertEqual(
            pruefe_zitate(antwort, P06_FUNDSTELLEN),
            {"erkannt": [], "unbekannt": []},
        )

    def test_p06_meldet_nur_den_nicht_uebergebenen_zeilenbereich(self):
        antwort = f"Nicht belegt: Öffnungszeit. (Fundstellen: {RACK}:6-10, {FRAESE}:7-8)"

        # Die beiden Rack-Bereiche 6-7 und 9-10 sind bekannt, aber 6-10 nicht.
        # Der Fräsenabsatz stand im Prompt. Seinen Inhalt prüft die Funktion nicht.
        self.assertEqual(
            pruefe_zitate(antwort, P06_FUNDSTELLEN),
            {
                "erkannt": [f"{RACK}:6-10", f"{FRAESE}:7-8"],
                "unbekannt": [f"{RACK}:6-10"],
            },
        )