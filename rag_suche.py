"""Sucht zu einer Frage passende Absätze im RAG-Suchbestand."""

from threading import Lock
from time import perf_counter

from rag_embeddings import lade_e5_modell


_kodiersperre = Lock()


def suche_fuer_frage(frage, top_k=None):
    """Gibt Fundstellen, E5-Ladedauer und Suchdauer in Millisekunden zurück."""
    # Den PostgreSQL-Adapter brauchen wir erst, wenn wirklich gesucht wird.
    from rag_db import suche_abschnitte

    # Miss die Zeit, bis E5 bereit ist. Ein vorhandenes Modell ist sofort verfügbar.
    e5_start = perf_counter()
    modell = lade_e5_modell()
    e5_load_ms = round((perf_counter() - e5_start) * 1_000)

    # Die Absatzvektoren liegen schon in PostgreSQL. E5 kodiert nur die Frage.
    suchstart = perf_counter()
    # Jeweils eine Frage nutzt das gemeinsame Modell. Die Datenbankabfrage
    # läuft anschließend außerhalb der Sperre.
    with _kodiersperre:
        fragevektor = modell.encode(f"query: {frage}", normalize_embeddings=True)
    treffer = suche_abschnitte(fragevektor, top_k)
    retrieval_ms = round((perf_counter() - suchstart) * 1_000)

    # Die aufrufende Datei entscheidet, ob und wie sie die Treffer anzeigt.
    return treffer, e5_load_ms, retrieval_ms
