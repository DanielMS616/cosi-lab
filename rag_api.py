"""Lokaler HTTP-Zugang zu gespeicherten RAG-Läufen."""

import sqlite3
from json import JSONDecodeError
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path

from rag_run_storage import RUN_DATABASE, load_rag_run


app = FastAPI(title="Cosi-Lab RAG-API")

# Die Lauf-ID ist in SQLite eine vorzeichenbehaftete 64-Bit-Ganzzahl.
# GROESSTE_LAUF_ID = 2**63 - 1 ist die größte Lauf-ID,
# die SQLite als INTEGER PRIMARY KEY speichern kann: 9_223_372_036_854_775_807
GROESSTE_LAUF_ID = 2**63 - 1


@app.get("/rag/laeufe/{lauf_id}")
def lese_rag_lauf(lauf_id: Annotated[int, Path(ge=1, le=GROESSTE_LAUF_ID)]):
    """Liest einen gespeicherten RAG-Lauf und gibt ihn als JSON zurück."""
    # Wenn es noch keine Datenbank gibt, gibt es auch keinen gespeicherten Lauf.
    if not RUN_DATABASE.exists():
        raise HTTPException(status_code=404, detail="Es gibt noch keine RAG-Läufe.")

    try:
        # Dieselbe Lesefunktion wie in show_rag_run.py öffnet SQLite schreibgeschützt.
        lauf = load_rag_run(RUN_DATABASE, lauf_id)
    except (sqlite3.Error, JSONDecodeError) as fehler:
        # Ein Lesefehler ist etwas anderes als eine unbekannte ID.
        raise HTTPException(
            status_code=500, detail="Der RAG-Lauf konnte nicht gelesen werden."
        ) from fehler

    if lauf is None:
        raise HTTPException(status_code=404, detail=f"RAG-Lauf {lauf_id} nicht gefunden.")

    # FastAPI wandelt das Dictionary in eine JSON-Antwort um.
    return lauf