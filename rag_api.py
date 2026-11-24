"""Lokaler HTTP-Zugang zu RAG-Vorschau, Antworten und gespeicherten Läufen."""

import sqlite3
from json import JSONDecodeError
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field

from rag_ablauf import beantworte_und_speichere
from rag_embeddings import E5_MODELL
from rag_prompt import baue_prompt
from rag_run_storage import RUN_DATABASE, load_rag_run


app = FastAPI(title="Cosi-Lab RAG-API")

# Die Lauf-ID ist in SQLite eine vorzeichenbehaftete 64-Bit-Ganzzahl.
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


class AntwortAnfrage(VorschauAnfrage):
    """Ergänzt Frage und Trefferzahl um die Wahl des Anbieters."""

    anbieter: Literal["gpt", "gemini"]


def suche_fuer_api(frage, top_k):
    """Ruft die gemeinsame Suche auf und meldet Datenbankfehler per HTTP."""
    # Erst hier die Suchabhängigkeiten laden. Der Abruf aus SQLite braucht sie nicht.
    from psycopg import OperationalError
    from psycopg.errors import UndefinedTable

    from rag_suche import suche_fuer_frage

    try:
        return suche_fuer_frage(frage, top_k)
    except SystemExit as fehler:
        # Die bisherige Suche beendet die CLI, wenn das Datenbankpasswort fehlt.
        # Hier melden wir den Fehler per HTTP, damit der Server weiterläuft.
        raise HTTPException(
            status_code=503, detail="Prüfe RAG_POSTGRES_PASSWORD in der lokalen .env."
        ) from fehler
    except (OperationalError, UndefinedTable) as fehler:
        raise HTTPException(
            status_code=503, detail="Prüfe PostgreSQL und führe bei Bedarf rag_import.py aus."
        ) from fehler


def bereite_rag_anfrage_vor(anfrage):
    """Bereitet Fundstellen und Prompt für beide POST-Endpunkte vor."""
    # Leerzeichen am Rand entfernen. Eine leere Frage soll keine Suche auslösen.
    frage = anfrage.frage.strip()
    if not frage:
        raise HTTPException(status_code=422, detail="Die Frage darf nicht leer sein.")

    # Beim Speichern des Laufs brauchen wir zusätzlich die beiden Messwerte.
    fundstellen, e5_load_ms, retrieval_ms = suche_fuer_api(frage, anfrage.top_k)

    # Ein leerer Suchbestand liefert keine Fundstellen und deshalb keinen Prompt.
    prompt = baue_prompt(frage, fundstellen) if fundstellen else None
    vorschau = {
        "frage": frage,
        "top_k": anfrage.top_k,
        "fundstellen": fundstellen,
        "prompt": prompt,
    }
    return vorschau, e5_load_ms, retrieval_ms


@app.post("/rag/vorschau")
def erstelle_vorschau(anfrage: VorschauAnfrage):
    """Zeigt Fundstellen und Prompt, ohne ein Antwortmodell aufzurufen."""
    vorschau, _, _ = bereite_rag_anfrage_vor(anfrage)
    return vorschau


@app.post("/rag/antwort")
def erstelle_antwort(anfrage: AntwortAnfrage):
    """Beantwortet eine Frage anhand der Fundstellen und speichert den Lauf."""
    vorschau, e5_load_ms, retrieval_ms = bereite_rag_anfrage_vor(anfrage)

    # Übernimm die Vorschau und ergänze die Felder für die Modellantwort.
    # None wird im JSON als null ausgegeben.
    antwortdaten = {
        **vorschau,
        "anbieter": anfrage.anbieter,
        "modell": None,
        "antwort": None,
        "zitatpruefung": None,
        "lauf_id": None,
    }
    if not vorschau["fundstellen"]:
        # Ohne Fundstellen gibt es keinen Modellaufruf und keinen neuen Lauf.
        return antwortdaten

    # Dieselbe Funktion wie in der CLI: aufrufen, Zitate prüfen, speichern.
    ergebnis, zitatpruefung, lauf_id = beantworte_und_speichere(
        vorschau["frage"],
        vorschau["prompt"],
        vorschau["fundstellen"],
        anbieter=anfrage.anbieter,
        top_k=anfrage.top_k,
        suchmodell=E5_MODELL,
        e5_load_ms=e5_load_ms,
        retrieval_ms=retrieval_ms,
        database_path=RUN_DATABASE,
    )

    # Fülle die Antwortfelder mit den Ergebnissen des gespeicherten Laufs.
    antwortdaten.update(
        modell=ergebnis["model"],
        antwort=ergebnis["text"],
        zitatpruefung=zitatpruefung,
        lauf_id=lauf_id,
    )
    return antwortdaten
