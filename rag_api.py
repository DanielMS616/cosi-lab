"""Lokaler HTTP-Zugang zu gespeicherten RAG-Läufen."""

import sqlite3

from json import JSONDecodeError
from typing import Annotated
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Path

from rag_prompt import baue_prompt
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


class VorschauAnfrage(BaseModel):
    """Beschreibt die JSON-Daten, die die Vorschau erwartet."""

    frage: str

    # Standard: drei Treffer. Die API gibt höchstens 20 Fundstellen zurück.
    top_k: int = Field(default=3, ge=1, le=20, strict=True)


@app.post("/rag/vorschau")
def erstelle_vorschau(anfrage: VorschauAnfrage):
    """Sucht Fundstellen und baut daraus den Prompt für die Vorschau."""
    # Leerzeichen am Rand entfernen. Eine leere Frage soll keine Suche auslösen.
    frage = anfrage.frage.strip()
    if not frage:
        raise HTTPException(status_code=422, detail="Die Frage darf nicht leer sein.")

    # Erst hier die Suchabhängigkeiten laden. Der Abruf aus SQLite braucht sie nicht.
    from psycopg import OperationalError
    from psycopg.errors import UndefinedTable

    from rag_suche import suche_fuer_frage

    try:
        # Dieselbe Suche wie in der CLI. Für die Vorschau genügen die Fundstellen.
        fundstellen, _, _ = suche_fuer_frage(frage, anfrage.top_k)
    except SystemExit as fehler:
        # Die bisherige Suche beendet die CLI, wenn das Datenbankpasswort fehlt.
        # Hier melden wir den Fehler per HTTP, damit der Server weiterläuft.
        raise HTTPException(
            status_code=503, detail="Prüfe RAG_POSTGRES_PASSWORD in der lokalen .env."
        ) from fehler
    except (OperationalError, UndefinedTable) as fehler:
        raise HTTPException(
            status_code=503,
            detail="Prüfe PostgreSQL und führe bei Bedarf rag_import.py aus.",
        ) from fehler

    # Ein leerer Suchbestand liefert keine Fundstellen und deshalb keinen Prompt.
    prompt = baue_prompt(frage, fundstellen) if fundstellen else None
    return {
        "frage": frage,
        "top_k": anfrage.top_k,
        "fundstellen": fundstellen,
        "prompt": prompt,
    }