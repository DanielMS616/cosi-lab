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
    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        max_output_tokens=120,
    )

    return response.output_text