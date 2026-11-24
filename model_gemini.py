import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from httpx import Client, NetworkError, ProxyError, RemoteProtocolError, TimeoutException

from modell_fehler import (
    ModellschluesselFehlt,
    ModellverbindungFehlgeschlagen,
    ModellzeitUeberschritten,
)


GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_TIMEOUT_SEKUNDEN = 30


def generate_gemini_report(prompt, *, max_output_tokens=120):
    """Sendet den Temperaturprompt an Gemini und gibt die Antwort zurück."""

    # Lade den Gemini-Schlüssel aus der .env neben dieser Datei.
    load_dotenv(Path(__file__).with_name(".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # Derselbe Fehlertyp wie bei GPT, damit die API beide Fälle erkennt.
        raise ModellschluesselFehlt("GEMINI_API_KEY fehlt. Prüfe die lokale .env.")

    try:
        # Gib Gemini einen HTTPX-Client vor. So wissen wir, welche Fehlertypen
        # bei einem Netzwerkproblem ankommen. Der with-Block schließt ihn wieder.
        with Client(timeout=GEMINI_TIMEOUT_SEKUNDEN, follow_redirects=True) as http_client:
            client = genai.Client(
                api_key=api_key,
                # Gemini erwartet das Zeitlimit in Millisekunden.
                http_options=types.HttpOptions(
                    httpx_client=http_client,
                    timeout=GEMINI_TIMEOUT_SEKUNDEN * 1_000,
                ),
            )
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(max_output_tokens=max_output_tokens),
            )
    except TimeoutException as fehler:
        raise ModellzeitUeberschritten("Zeitlimit beim Gemini-Aufruf überschritten.") from fehler
    except (NetworkError, ProxyError, RemoteProtocolError) as fehler:
        raise ModellverbindungFehlgeschlagen("Verbindung zu Gemini fehlgeschlagen.") from fehler

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
