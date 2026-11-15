from datetime import datetime, timezone

from doc_prompt import check_citations
from doc_storage import initialize_doc_database, save_doc_run

def generate_doc_answer(prompt, *, provider):
    """Sendet einen fertigen Dokuprompt an den gewählten Anbieter."""

    # Lade nur den Adapter, der für diesen Aufruf gebraucht wird.
    if provider == "gpt":
        from model_gpt import generate_gpt_report

        generate = generate_gpt_report
        model_name = "gpt-4o-mini"
    elif provider == "gemini":
        from model_gemini import GEMINI_MODEL, generate_gemini_report

        generate = generate_gemini_report
        model_name = GEMINI_MODEL
    else:
        raise ValueError(f"Unbekannter Modellanbieter: {provider}")

    # Der Zeitstempel gehört zum Start des Aufrufs, nicht zur Rückkehr.
    requested_at_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    result = generate(prompt, max_output_tokens=240)

    # Adapterdaten übernehmen und um Modellname und Aufrufzeitpunkt ergänzen.
    # **result übernimmt die Felder aus dem Adapter-Ergebnis in das zurückgegebene Dictionary.
    return {
        **result,
        "model": model_name,
        "requested_at_utc": requested_at_utc,
    }


def answer_and_save_doc_question(question, prompt, hits, *, provider, database_path):
    """Beantwortet eine vorbereitete Dokufrage und speichert den Lauf."""
    result = generate_doc_answer(prompt, provider=provider)

    # Prüfe die Antwort gegen genau die Fundstellen aus dem gesendeten Prompt.
    citations = check_citations(result["text"], hits)

    # Erst nach der Modellantwort wird die Datenbank angelegt oder ergänzt.
    initialize_doc_database(database_path)
    run_id = save_doc_run(
        database_path,
        model=result["model"],
        requested_at_utc=result["requested_at_utc"],
        question=question,
        prompt=prompt,
        hits=hits,
        response_text=result["text"],
        citations=citations,
        api_status=result.get("status"),
        incomplete_reason=result.get("incomplete_reason"),
    )

    return {**result, "citations": citations, "run_id": run_id}