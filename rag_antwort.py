"""Sendet einen fertigen RAG-Prompt an das gewählte Antwortmodell."""

from datetime import datetime, timezone
from time import perf_counter


def rufe_antwortmodell_auf(prompt, anbieter, *, max_output_tokens):
    """Liefert die Modellantwort zusammen mit den Daten zum Aufruf."""
    # Lade nur den Adapter für den ausgewählten Anbieter.
    if anbieter == "gpt":
        from model_gpt import GPT_MODEL, generate_gpt_report

        antwort_funktion = generate_gpt_report
        antwortmodell = GPT_MODEL
    elif anbieter == "gemini":
        from model_gemini import GEMINI_MODEL, generate_gemini_report

        antwort_funktion = generate_gemini_report
        antwortmodell = GEMINI_MODEL
    else:
        raise ValueError(f"Unbekannter Modellanbieter: {anbieter}")

    # Merke den Startzeitpunkt in UTC. Miss die Dauer des Adapteraufrufs
    # separat und rechne die gemessenen Sekunden in Millisekunden um.
    requested_at_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    api_start = perf_counter()
    ergebnis = antwort_funktion(prompt, max_output_tokens=max_output_tokens)
    client_duration_ms = round((perf_counter() - api_start) * 1_000)

    # **ergebnis übernimmt alle Felder des Adapters, etwa Text und Tokenzahlen.
    # Die drei weiteren Felder beschreiben den Aufruf selbst.
    return {
        **ergebnis,
        "model": antwortmodell,
        "requested_at_utc": requested_at_utc,
        "client_duration_ms": client_duration_ms,
    }