import sqlite3

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Annotated, Literal
from openai import APIConnectionError
from pathlib import Path
from fastapi.responses import FileResponse
from google.genai.errors import ServerError as GeminiServerError

from doc_storage import list_doc_runs, load_doc_run
from doc_answer import answer_and_save_doc_question
from doc_prompt import build_doc_prompt, build_multi_doc_prompt
from doc_search import DOC_DATABASE_PATH, PROJECT_DOCS, find_top_excerpts_in_files

app = FastAPI(title="Cosi-Lab")


class DocQuestion(BaseModel):
    """Beschreibt, welche Angaben im JSON der Anfrage stehen."""
    question: str
    multi_source: bool = False


class DocAnswerRequest(DocQuestion):
    """Eine Dokufrage mit ausdrücklich gewähltem Modellanbieter."""
    provider: Literal["gpt", "gemini"]


def prepare_doc_question(request: DocQuestion):
    # Leerzeichen allein sind keine Frage. Den Originaltext behalten wir.
    question = request.question
    if not question.strip():
        raise HTTPException(status_code=422, detail="Die Frage darf nicht leer sein.")

    # Dieselbe Suche wie im Terminal, mit der festgelegten Dokumentliste.
    hits = find_top_excerpts_in_files(PROJECT_DOCS, question)
    if not request.multi_source:
        hits = hits[:1]

    # Auch eine Suche ohne Treffer ist regulär. Dann gibt es keinen Prompt.
    if not hits:
        return {"question": question, "sources": [], "prompt": None}

    if len(hits) == 1:
        prompt = build_doc_prompt(question, hits[0])
    else:
        prompt = build_multi_doc_prompt(question, hits)

    return {"question": question, "sources": hits, "prompt": prompt}


@app.post("/doc-questions/preview")
def preview_doc_question(request: DocQuestion):
    return prepare_doc_question(request)


@app.post("/doc-questions/answer")
def answer_doc_question(request: DocAnswerRequest):
    # Beide Endpunkte wählen die Fundstellen und bauen den Prompt gleich.
    response = {
        **prepare_doc_question(request),
        "provider": request.provider,
        "model": None,
        "answer": None,
        "citations": None,
        "api_status": None,
        "incomplete_reason": None,
        "run_id": None,
    }

    # Ohne Fundstelle gibt es weder eine Modellanfrage noch einen Eintrag.
    if not response["sources"]:
        return response

    try:
        result = answer_and_save_doc_question(
            response["question"],
            response["prompt"],
            response["sources"],
            provider=request.provider,
            database_path=DOC_DATABASE_PATH,
        )
    except APIConnectionError as error:
        # Gib dem Client eine verständliche Meldung ohne SDK-Details.
        raise HTTPException(
            status_code=502,
            detail="Der Modellanbieter ist derzeit nicht erreichbar.",
        ) from error
    
    except GeminiServerError as error:
        # Nur einen Gemini-Ausfall mit HTTP 503 behandeln wir hier gezielt.
        if error.code != 503:
            raise

        # Gib dem Browser einen verständlichen Hinweis zum Ausfall.
        raise HTTPException(
            status_code=503,
            detail="Gemini ist vorübergehend nicht verfügbar.",
        ) from error

    # Ergänze die Felder erst, wenn die Antwort samt Lauf-ID vorliegt.
    response.update(
        model=result["model"],
        answer=result["text"],
        citations=result["citations"],
        api_status=result.get("status"),
        incomplete_reason=result.get("incomplete_reason"),
        run_id=result["run_id"],
    )
    return response


@app.get("/doc-runs")
def read_doc_runs(limit: Annotated[int, Query(ge=1, le=100)] = 10):
    """Liefert eine Übersicht der zuletzt gespeicherten Dokuläufe."""
    try:
        # Sortierung und Begrenzung übernimmt die getestete SQLite-Funktion.
        runs = list_doc_runs(DOC_DATABASE_PATH, limit=limit)
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=500,
            detail="Dokuläufe konnten nicht gelesen werden.",
        ) from error

    return {"runs": runs}


@app.get("/doc-runs/{run_id}")
def read_doc_run(run_id: int):
    """Gibt einen gespeicherten Dokulauf anhand seiner ID zurück."""
    try:
        # Dieselbe schreibgeschützte Lesefunktion wie in show_doc_run.py.
        run = load_doc_run(DOC_DATABASE_PATH, run_id)
    except sqlite3.Error as error:
        # Ein Datenbankfehler ist etwas anderes als eine unbekannte Lauf-ID.
        raise HTTPException(
            status_code=500,
            detail="Dokuläufe konnten nicht gelesen werden.",
        ) from error

    if run is None:
        raise HTTPException(
            status_code=404,
            detail=f"Kein Dokulauf mit ID {run_id} gefunden.",
        )

    return run


@app.get("/", include_in_schema=False)
def show_doc_ui():
    # Der Dateipfad beginnt beim Ordner, in dem doc_api.py liegt.
    page = Path(__file__).resolve().parent / "web" / "index.html"
    return FileResponse(page, media_type="text/html")