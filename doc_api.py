from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from doc_prompt import build_doc_prompt, build_multi_doc_prompt
from doc_search import PROJECT_DOCS, find_top_excerpts_in_files

app = FastAPI(title="Cosi-Lab")


class DocQuestion(BaseModel):
    """Beschreibt, welche Angaben im JSON der Anfrage stehen."""
    question: str
    multi_source: bool = False


@app.post("/doc-questions/preview")
def preview_doc_question(request: DocQuestion):
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