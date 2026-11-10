from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def generate_gpt_report(prompt):
    """Sendet den Temperaturprompt an GPT und gibt die Antwort als Text zurück."""

    # __file__ ist der Pfad zu model_gpt.py. Die .env liegt direkt daneben.
    env_path = Path(__file__).with_name(".env")
    load_dotenv(env_path)

    # Der Client liest OPENAI_API_KEY aus der Python-Umgebung.
    # Bei einem Fehler versucht er es nicht automatisch erneut.
    client = OpenAI(max_retries=0)

    # Der Prompt enthält bereits den Schreibauftrag und die berechneten Zahlen.
    raw_response = client.responses.with_raw_response.create(
        model="gpt-4o-mini",
        input=prompt,
        max_output_tokens=120,
    )

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
    }