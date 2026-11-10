import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


GEMINI_MODEL = "gemini-3.5-flash-lite"


def generate_gemini_report(prompt):
    """Sendet den Temperaturprompt an Gemini und gibt die Antwort zurück."""

    # Lade den Gemini-Schlüssel aus der .env neben dieser Datei.
    load_dotenv(Path(__file__).with_name(".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY fehlt. Prüfe die lokale .env.")

    client = genai.Client(api_key=api_key)

    # contents enthält denselben Schreibauftrag und dieselben Fakten wie bei GPT.
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=120),
    )

    report = response.text
    if not report or not report.strip():
        raise ValueError("Gemini hat keinen Berichtstext geliefert.")

    # Die Tokenzahlen kommen mit derselben API-Antwort wie der Bericht.
    usage = response.usage_metadata

    return {
        "text": report,
        "processing_ms": None,
        "input_tokens": usage.prompt_token_count if usage is not None else None,
        "output_tokens": usage.candidates_token_count if usage is not None else None,
    }