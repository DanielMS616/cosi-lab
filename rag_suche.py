"""Sucht zu einer Frage passende Absätze im RAG-Suchbestand."""

from time import perf_counter

from rag_embeddings import lade_e5_modell


def suche_fuer_frage(frage, top_k=None):
    """Gibt die Treffer, die E5-Ladedauer und die Suchdauer zurück."""
    # Den PostgreSQL-Adapter brauchen wir erst, wenn wirklich gesucht wird.
    from rag_db import suche_abschnitte

    # Miss, wie lange das Laden des E5-Modells dauert.
    e5_start = perf_counter()
    modell = lade_e5_modell()
    e5_load_ms = round((perf_counter() - e5_start) * 1_000)

    # Die Absatzvektoren liegen schon in PostgreSQL.
    # E5 berechnet für diese Suche deshalb nur den Vektor der Frage.
    suchstart = perf_counter()
    fragevektor = modell.encode(f"query: {frage}", normalize_embeddings=True)
    treffer = suche_abschnitte(fragevektor, top_k)

    # Die Suchdauer umfasst den Fragevektor und die Datenbankabfrage.
    retrieval_ms = round((perf_counter() - suchstart) * 1_000)

    # Die aufrufende Datei entscheidet, wie sie die Treffer anzeigt.
    return treffer, e5_load_ms, retrieval_ms