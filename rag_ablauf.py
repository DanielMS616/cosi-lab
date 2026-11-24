"""Verbindet Modellaufruf, Zitatprüfung und Speicherung eines RAG-Laufs."""

from rag_antwort import rufe_antwortmodell_auf
from rag_run_storage import RUN_DATABASE, save_rag_run
from rag_zitate import pruefe_zitate


# Das * bedeutet: Ab anbieter werden die Argumente mit ihrem Namen übergeben.
# So sieht man beim Aufruf zum Beispiel direkt, welche Zahl die Ladezeit und welche die Suchdauer ist.
def beantworte_und_speichere(
    frage,
    prompt,
    fundstellen,
    *,
    anbieter,
    top_k,
    suchmodell,
    e5_load_ms,
    retrieval_ms,
    database_path=RUN_DATABASE,
):
    """Gibt Modellantwort, Ergebnis der Zitatprüfung und SQLite-Lauf-ID zurück."""
    # 1. Sende den vorbereiteten Prompt an GPT oder Gemini.
    token_limit = 240
    ergebnis = rufe_antwortmodell_auf(
        prompt, anbieter, max_output_tokens=token_limit
    )

    # 2. Prüfe Zitate nur gegen die Ausschnitte, die im Prompt standen.
    zitatpruefung = pruefe_zitate(ergebnis["text"], fundstellen)

    # 3. Halte fest, was wir gesendet und was wir zurückbekommen haben.
    # .get() liefert None für Angaben, die der Anbieter nicht meldet.
    # In SQLite erscheinen diese Angaben dann als NULL.
    lauf = {
        "requested_at_utc": ergebnis["requested_at_utc"],
        "question": frage,
        "top_k": top_k,
        "retrieval_model": suchmodell,
        "provider": anbieter,
        "model": ergebnis["model"],
        "max_output_tokens": token_limit,
        "prompt": prompt,
        "response_text": ergebnis["text"],
        "input_tokens": ergebnis.get("input_tokens"),
        "output_tokens": ergebnis.get("output_tokens"),
        "e5_load_ms": e5_load_ms,
        "retrieval_ms": retrieval_ms,
        "client_duration_ms": ergebnis["client_duration_ms"],
        "provider_duration_ms": ergebnis.get("processing_ms"),
        "api_status": ergebnis.get("status"),
        "incomplete_reason": ergebnis.get("incomplete_reason"),
    }
    lauf_id = save_rag_run(database_path, lauf, fundstellen)

    # Die CLI entscheidet, wie sie Antwort, Zitatprüfung und ID anzeigt.
    return ergebnis, zitatpruefung, lauf_id