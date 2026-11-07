"""Request text once from the OpenAI Responses API using the standard library."""

import http.client
import json
import os
import ssl
import time
from contextlib import closing
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAITextResult:
    """Keep usable text and independently validated metadata from one request.

    A dataclass supplies named fields and an initializer without hand-written
    boilerplate. frozen=True prevents accidental changes to a received result.
    None means metadata was absent or invalid, not that its value was zero.
    """

    text: str
    requested_model: str
    returned_model: str | None
    response_id: str | None
    request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    duration_ms: float


class OpenAITextError(Exception):
    """Report adapter failures without exposing credentials or server error text."""

    ERROR_CODES = frozenset({
        "unknown", "invalid_input", "configuration_error", "http_error", "timeout",
        "connection_error", "invalid_json", "invalid_response", "incomplete_response",
        "empty_response", "refusal",
    })

    def __init__(
        self, message: str, *, error_code: str = "unknown", http_status: int | None = None
    ) -> None:
        """Keep legacy messages and attach only a fixed code and optional numeric status.

        Unknown code values fall back to unknown, so arbitrary diagnostic text
        cannot enter the structured code field. Callers supply a status only when
        an HTTP response has actually been received; never infer it from an error.
        """
        super().__init__(message)
        self.error_code = (
            error_code if isinstance(error_code, str) and error_code in self.ERROR_CODES else "unknown"
        )
        self.http_status = (
            http_status if isinstance(http_status, int) and not isinstance(http_status, bool) else None
        )


def _reject_json_constant(value: str) -> None:
    """Reject NaN and Infinity, which Python accepts but JSON does not allow."""
    raise ValueError("Invalid JSON constant.")


def _parse_response(body: bytes, *, http_status: int | None = None) -> dict[str, object]:
    """Decode the body once so text and metadata use the same JSON object."""
    try:
        response = json.loads(body.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError):
        raise OpenAITextError(
            "Die API-Antwort enthält kein gültiges UTF-8-JSON.",
            error_code="invalid_json", http_status=http_status
        ) from None

    if not isinstance(response, dict):
        raise OpenAITextError(
            "Die API-Antwort hat ein ungültiges Format.",
            error_code="invalid_response", http_status=http_status
        )
    return response


def _extract_text(response: dict[str, object], *, http_status: int | None = None) -> str:
    """Join completed text or classify failure, retaining only a received HTTP status."""
    if response.get("status") != "completed":
        raise OpenAITextError(
            "Die API-Antwort ist nicht vollständig abgeschlossen.",
            error_code="incomplete_response", http_status=http_status
        )
    if response.get("error") is not None or response.get("incomplete_details") is not None:
        error_code = "incomplete_response" if response.get("incomplete_details") is not None else "invalid_response"
        raise OpenAITextError(
            "Die API-Antwort meldet einen Fehler oder unvollständige Ausgabe.",
            error_code=error_code, http_status=http_status,
        )

    output = response.get("output")
    if not isinstance(output, list):
        raise OpenAITextError(
            "Der API-Antwort fehlt eine gültige Ausgabeliste.",
            error_code="invalid_response", http_status=http_status
        )

    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            raise OpenAITextError(
                "Die API-Antwort enthält einen ungültigen Ausgabeeintrag.",
                error_code="invalid_response", http_status=http_status
            )
        # Output may start with reasoning or tool calls rather than a message.
        if item.get("type") != "message":
            continue
        if "status" in item and item["status"] != "completed":
            raise OpenAITextError(
                "Eine Nachricht der API-Antwort ist nicht abgeschlossen.",
                error_code="incomplete_response", http_status=http_status
            )
        content = item.get("content")
        if not isinstance(content, list):
            raise OpenAITextError(
                "Eine API-Nachricht enthält keine gültige Inhaltsliste.",
                error_code="invalid_response", http_status=http_status
            )
        for part in content:
            if not isinstance(part, dict):
                raise OpenAITextError(
                    "Eine API-Nachricht enthält einen ungültigen Inhalt.",
                    error_code="invalid_response", http_status=http_status
                )
            if part.get("type") == "refusal":
                raise OpenAITextError(
                    "Das Modell hat die Bearbeitung des Auftrags abgelehnt.",
                    error_code="refusal", http_status=http_status
                )
            if part.get("type") == "output_text":
                text = part.get("text")
                if not isinstance(text, str):
                    raise OpenAITextError(
                        "Ein Textinhalt der API-Antwort ist kein Text.",
                        error_code="invalid_response", http_status=http_status
                    )
                text_parts.append(text)

    # Preserve the generated text, including whitespace, without extra separators.
    result = "".join(text_parts)
    if not result.strip():
        raise OpenAITextError(
            "Die API-Antwort enthält keinen nichtleeren Text.",
            error_code="empty_response", http_status=http_status
        )
    return result


def _optional_text(value: object) -> str | None:
    """Retain nonblank strings unchanged; ignore other optional metadata."""
    if isinstance(value, str) and value.strip():
        return value
    return None


def _optional_token_count(value: object) -> int | None:
    """Accept nonnegative integers, excluding bool (an int subclass in Python)."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def generate_text_result(prompt: str, *, model: str = "gpt-4.1-mini") -> OpenAITextResult:
    """Send one prompt and return text with metadata, or raise OpenAITextError.

    Read OPENAI_API_KEY only when called. Use one HTTPS POST with normal TLS
    verification, no retries and no redirects. The 30-second network timeout
    limits blocking socket operations; it is not an overall execution deadline.
    Request at most 600 output tokens and disable response storage with store=False.
    Explicit refusals raise OpenAITextError even when other parts contain text.
    Errors deliberately omit server bodies and underlying exception messages.
    Each error carries a fixed code and the received HTTP status, if available.
    Returned text is not checked for factual correctness.
    Optional metadata never substitutes for text validation. Invalid fields stay
    None independently; token totals are neither inferred nor recalculated.
    duration_ms measures local HTTP setup, request, reading and resource closing
    with a monotonic clock, excluding input validation and JSON/text processing.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise OpenAITextError("Der Auftrag muss ein nichtleerer Text sein.", error_code="invalid_input")
    if not isinstance(model, str) or not model.strip():
        raise OpenAITextError("Der Modellname muss ein nichtleerer Text sein.", error_code="invalid_input")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        raise OpenAITextError("OPENAI_API_KEY fehlt oder ist leer.", error_code="configuration_error")
    # Reject invalid header characters locally, without including the key in errors.
    if not api_key.isascii() or not api_key.isprintable() or any(char.isspace() for char in api_key):
        raise OpenAITextError("OPENAI_API_KEY enthält ungültige Zeichen.", error_code="configuration_error")

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

    http_status = None
    started_at = time.perf_counter()
    try:
        # HTTPSConnection does not follow redirects or retry requests. The default
        # SSL context verifies both the certificate chain and the server hostname.
        context = ssl.create_default_context()
        with closing(http.client.HTTPSConnection(
            "api.openai.com", timeout=30, context=context
        )) as connection:
            connection.request("POST", "/v1/responses", body=body, headers=headers)
            with connection.getresponse() as response:
                # Retain only the status from this actual HTTP response.
                http_status = response.status
                if not 200 <= response.status < 300:
                    # Do not read or expose the server's error body or headers.
                    raise OpenAITextError(
                        f"Die API-Anfrage ist fehlgeschlagen (HTTP {response.status}).",
                        error_code="http_error", http_status=http_status,
                    )
                response_body = response.read()
                request_id = _optional_text(response.getheader("x-request-id"))
    except TimeoutError:
        raise OpenAITextError(
            "Zeitüberschreitung bei der API-Verbindung.",
            error_code="timeout", http_status=http_status
        ) from None
    except (OSError, http.client.HTTPException):
        # Suppress chained messages because they may contain sensitive input.
        raise OpenAITextError(
            "Die API-Verbindung ist fehlgeschlagen.",
            error_code="connection_error", http_status=http_status
        ) from None

    duration_ms = (time.perf_counter() - started_at) * 1000
    response_data = _parse_response(response_body, http_status=http_status)
    text = _extract_text(response_data, http_status=http_status)
    usage = response_data.get("usage")
    if not isinstance(usage, dict):
        usage = {}

    return OpenAITextResult(
        text=text,
        requested_model=model,
        returned_model=_optional_text(response_data.get("model")),
        response_id=_optional_text(response_data.get("id")),
        request_id=request_id,
        input_tokens=_optional_token_count(usage.get("input_tokens")),
        output_tokens=_optional_token_count(usage.get("output_tokens")),
        total_tokens=_optional_token_count(usage.get("total_tokens")),
        duration_ms=duration_ms,
    )


def generate_text(prompt: str, *, model: str = "gpt-4.1-mini") -> str:
    """Return only text through the same single-request path and error handling.

    Keep the existing signature for CLI and prompt-comparison callers. See
    generate_text_result for request limits, diagnostics and validation rules.
    """
    return generate_text_result(prompt, model=model).text
