import os
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, OpenAI

from modell_fehler import (
    ModellschluesselFehlt,
    ModellverbindungFehlgeschlagen,
    ModellzeitUeberschritten,
)


GPT_MODEL = "gpt-4o-mini"


def generate_gpt_report(prompt, *, max_output_tokens=120):
    """Sendet den Temperaturprompt an GPT und gibt die Antwort als Text zurück."""

    # __file__ ist der Pfad zu model_gpt.py. Die .env liegt direkt daneben.
    env_path = Path(__file__).with_name(".env")
    load_dotenv(env_path)

    # Melde einen fehlenden Schlüssel, bevor der SDK-Client erzeugt wird.
    # Der OpenAI-Client kennt beide Umgebungsvariablen.
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_ADMIN_KEY")):
        raise ModellschluesselFehlt("OPENAI_API_KEY fehlt. Prüfe die lokale .env.")

    # OpenAI erwartet das Zeitlimit in Sekunden. Automatische Wiederholungen
    # bleiben ausgeschaltet.
    client = OpenAI(max_retries=0, timeout=30.0)
    try:
        raw_response = client.responses.with_raw_response.create(
            model=GPT_MODEL,
            input=prompt,
            max_output_tokens=max_output_tokens,
        )
    except APITimeoutError as fehler:
        # Im OpenAI-SDK ist ein Timeout auch ein Verbindungsfehler.
        # Fange den spezielleren Fehler deshalb zuerst ab.
        raise ModellzeitUeberschritten("Zeitlimit beim GPT-Aufruf überschritten.") from fehler
    except APIConnectionError as fehler:
        raise ModellverbindungFehlgeschlagen("Verbindung zu GPT fehlgeschlagen.") from fehler

    # Der HTTP-Header liefert die Verarbeitungszeit als Text.
    try:
        processing_ms = int(raw_response.headers.get("openai-processing-ms"))
    except (TypeError, ValueError):
        processing_ms = None

    # Der Antwortinhalt enthält den Bericht und, falls vorhanden, die Tokenzahlen.
    response = raw_response.parse()
    usage = response.usage

    return {
        "text": response.output_text,
        "processing_ms": processing_ms,
        "input_tokens": usage.input_tokens if usage is not None else None,
        "output_tokens": usage.output_tokens if usage is not None else None,
        "status": response.status,
        "incomplete_reason": (
            response.incomplete_details.reason
            if response.incomplete_details is not None
            else None
        ),
    }
