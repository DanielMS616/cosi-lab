"""Request text once from the OpenAI Responses API using the standard library."""

import http.client
import json
import os
import ssl
from contextlib import closing


class OpenAITextError(Exception):
    """Report adapter failures without exposing credentials or server error text."""


def _reject_json_constant(value: str) -> None:
    """Reject NaN and Infinity, which Python accepts but JSON does not allow."""
    raise ValueError("Invalid JSON constant.")


def _extract_text(body: bytes) -> str:
    """Join completed output_text parts in order; reject any explicit refusal."""
    try:
        response = json.loads(body.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError):
        raise OpenAITextError("Die API-Antwort enthält kein gültiges UTF-8-JSON.") from None

    if not isinstance(response, dict):
        raise OpenAITextError("Die API-Antwort hat ein ungültiges Format.")
    if response.get("status") != "completed":
        raise OpenAITextError("Die API-Antwort ist nicht vollständig abgeschlossen.")
    if response.get("error") is not None or response.get("incomplete_details") is not None:
        raise OpenAITextError("Die API-Antwort meldet einen Fehler oder unvollständige Ausgabe.")

    output = response.get("output")
    if not isinstance(output, list):
        raise OpenAITextError("Der API-Antwort fehlt eine gültige Ausgabeliste.")

    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            raise OpenAITextError("Die API-Antwort enthält einen ungültigen Ausgabeeintrag.")
        # Output may start with reasoning or tool calls rather than a message.
        if item.get("type") != "message":
            continue
        if "status" in item and item["status"] != "completed":
            raise OpenAITextError("Eine Nachricht der API-Antwort ist nicht abgeschlossen.")
        content = item.get("content")
        if not isinstance(content, list):
            raise OpenAITextError("Eine API-Nachricht enthält keine gültige Inhaltsliste.")
        for part in content:
            if not isinstance(part, dict):
                raise OpenAITextError("Eine API-Nachricht enthält einen ungültigen Inhalt.")
            if part.get("type") == "refusal":
                raise OpenAITextError("Das Modell hat die Bearbeitung des Auftrags abgelehnt.")
            if part.get("type") == "output_text":
                text = part.get("text")
                if not isinstance(text, str):
                    raise OpenAITextError("Ein Textinhalt der API-Antwort ist kein Text.")
                text_parts.append(text)

    # Preserve the generated text, including whitespace, without extra separators.
    result = "".join(text_parts)
    if not result.strip():
        raise OpenAITextError("Die API-Antwort enthält keinen nichtleeren Text.")
    return result


def generate_text(prompt: str, *, model: str = "gpt-4.1-mini") -> str:
    """Send one prompt and return completed output text, or raise OpenAITextError.

    Read OPENAI_API_KEY only when called. Use one HTTPS POST with normal TLS
    verification, no retries and no redirects. The 30-second network timeout
    limits blocking socket operations; it is not an overall execution deadline.
    Request at most 600 output tokens and disable response storage with store=False.
    Explicit refusals raise OpenAITextError even when other parts contain text.
    Errors deliberately omit server bodies and underlying exception messages.
    Returned text is not checked for factual correctness.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise OpenAITextError("Der Auftrag muss ein nichtleerer Text sein.")
    if not isinstance(model, str) or not model.strip():
        raise OpenAITextError("Der Modellname muss ein nichtleerer Text sein.")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise OpenAITextError("OPENAI_API_KEY fehlt oder ist leer.")
    # Reject invalid header characters locally, without including the key in errors.
    if not api_key.isascii() or not api_key.isprintable() or any(char.isspace() for char in api_key):
        raise OpenAITextError("OPENAI_API_KEY enthält ungültige Zeichen.")

    payload = {
        "model": model,
        "input": prompt,
        "max_output_tokens": 600,
        "store": False,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        # HTTPSConnection does not follow redirects or retry requests. The default
        # SSL context verifies both the certificate chain and the server hostname.
        context = ssl.create_default_context()
        with closing(http.client.HTTPSConnection(
            "api.openai.com", timeout=30, context=context
        )) as connection:
            connection.request("POST", "/v1/responses", body=body, headers=headers)
            with connection.getresponse() as response:
                if not 200 <= response.status < 300:
                    # Do not read or expose the server's error body or headers.
                    raise OpenAITextError(f"Die API-Anfrage ist fehlgeschlagen (HTTP {response.status}).")
                response_body = response.read()
    except TimeoutError:
        raise OpenAITextError("Zeitüberschreitung bei der API-Verbindung.") from None
    except (OSError, http.client.HTTPException):
        # Suppress chained messages because they may contain sensitive input.
        raise OpenAITextError("Die API-Verbindung ist fehlgeschlagen.") from None

    return _extract_text(response_body)
