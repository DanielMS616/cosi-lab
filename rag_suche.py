"""Sucht zu einer Frage passende Absätze im RAG-Suchbestand."""

import re

from threading import Lock
from time import perf_counter

from rag_embeddings import lade_e5_modell


_kodiersperre = Lock()

# Die Wortgrenzen verhindern, dass P-17 auch auf P-170 passt.
KENNUNGSMUSTER = re.compile(r"\b(?:P|S)-[0-9]+\b")


def ziehe_kennung_vor(treffer, zielkennung):
    """Zieht Treffer vor, die die gesuchte Kennung im Absatz nennen."""
    passend = []
    rest = []

    for fundstelle in treffer:
        # Wir prüfen den Absatztext. Der Dateiname allein reicht nicht.
        kennungen = KENNUNGSMUSTER.findall(fundstelle["text"].upper())
        if zielkennung in kennungen:
            passend.append(fundstelle)
        else:
            rest.append(fundstelle)

    # Innerhalb beider Gruppen bleibt die E5-Reihenfolge erhalten.
    return passend + rest


def suche_fuer_frage(frage, top_k=None, *, kennung_vorziehen=False):
    """Gibt Fundstellen, E5-Ladedauer und Suchdauer in Millisekunden zurück."""
    # Den PostgreSQL-Adapter brauchen wir erst, wenn wirklich gesucht wird.
    from rag_db import suche_abschnitte

    # Miss die Zeit, bis E5 bereit ist. Ein vorhandenes Modell ist sofort verfügbar.
    e5_start = perf_counter()
    modell = lade_e5_modell()
    e5_load_ms = round((perf_counter() - e5_start) * 1_000)

    # Die Absatzvektoren liegen schon in PostgreSQL. E5 kodiert nur die Frage.
    suchstart = perf_counter()

    zielkennung = None
    suchlimit = top_k

    if kennung_vorziehen:
        kennungen = set(KENNUNGSMUSTER.findall(frage.upper()))
        # Bei mehreren Kennungen bevorzugen wir keine davon.
        if len(kennungen) == 1:
            zielkennung = kennungen.pop()
            if top_k is not None:
                suchlimit = max(top_k, 5)

    # Jeweils eine Frage nutzt das gemeinsame Modell. Die Datenbankabfrage
    # läuft anschließend außerhalb der Sperre.
    with _kodiersperre:
        fragevektor = modell.encode(f"query: {frage}", normalize_embeddings=True)
    treffer = suche_abschnitte(fragevektor, suchlimit)
    if zielkennung is not None:
        # Erst umsortieren, dann auf die gewünschte Trefferzahl kürzen.
        treffer = ziehe_kennung_vor(treffer, zielkennung)[:top_k]
    retrieval_ms = round((perf_counter() - suchstart) * 1_000)

    # Die aufrufende Datei entscheidet, ob und wie sie die Treffer anzeigt.
    return treffer, e5_load_ms, retrieval_ms
