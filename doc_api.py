from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal

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

    result = answer_and_save_doc_question(
        response["question"],
        response["prompt"],
        response["sources"],
        provider=request.provider,
        database_path=DOC_DATABASE_PATH,
    )

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