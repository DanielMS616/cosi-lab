"""Prepare a temperature-report request and call an injected text generator."""

import json
import math
from collections.abc import Callable


def _validate_number(value: int | float, name: str) -> None:
    """Reject nonnumeric content and nonfinite floats before building the request."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite int or float.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")


def generate_temperature_report(
    analysis_result: dict[str, int | float],
    threshold: int | float,
    text_generator: Callable[[str], str],
) -> str:
    """Ask the supplied function for a short German report of existing statistics.

    analysis_result comes from analyze_temperatures; threshold must be the
    threshold used for that analysis. The statistics are copied, never
    recalculated. Their consistency and their threshold association cannot
    be established here without the original measurements.

    Only the seven known numeric statistics and threshold enter the request.
    Extra dictionary entries are ignored; missing or nonnumeric facts raise
    ValueError before the generator is called.

    Call text_generator exactly once for a valid request and return its text
    unchanged. Non-text or blank responses raise ValueError. Generator
    exceptions propagate unchanged, without retries. This function does not
    check whether the response is factually correct or follows the request.
    """
    if not isinstance(analysis_result, dict):
        raise ValueError("analysis_result must be a dictionary of statistics.")

    # Select fields explicitly so paths, raw data, or other extra entries
    # cannot enter the request by serializing the entire input dictionary.
    statistic_names = (
        "total_count", "valid_count", "missing_count",
        "minimum", "maximum", "mean", "exceedance_count",
    )
    facts: dict[str, int | float] = {}
    for name in statistic_names:
        if name not in analysis_result:
            raise ValueError(f"Missing statistic: {name}.")
        value = analysis_result[name]
        _validate_number(value, name)
        facts[name] = value
    _validate_number(threshold, "threshold")
    facts["threshold"] = threshold

    prompt = (
        "Schreibe einen kurzen deutschen Temperaturbericht ausschließlich anhand "
        "der folgenden Kennzahlen. Übernimm die Kennzahlen, ohne sie neu zu berechnen.\n"
        "Gib alle sieben übergebenen Kennzahlen und den Schwellenwert wieder. "
        "Beschränke dich auf diese Fakten und die genannten Berechnungsregeln.\n"
        "total_count bezeichnet alle, valid_count die gültigen und missing_count "
        "die fehlenden Messwerte. Berücksichtige fehlende Messwerte ausdrücklich: "
        "Sie wurden nicht ersetzt und nicht in Minimum, Maximum oder Mittelwert einbezogen.\n"
        "minimum, maximum und mean sind Minimum, Maximum und arithmetischer "
        "Mittelwert der gültigen Temperaturen in °C; threshold ist der Schwellenwert in °C.\n"
        "exceedance_count zählt Werte strikt größer als threshold. Werte genau am "
        "Schwellenwert zählen nicht als Überschreitung.\n"
        "Leite keine zusätzlichen Aussagen über einzelne Temperaturen oder deren Häufigkeit ab. "
        "Triff insbesondere keine Aussage darüber, ob Messwerte genau am Schwellenwert "
        "vorkommen. Erläutere dazu nur die allgemeine Regel: Gleichheit zählt nicht "
        "als Überschreitung.\n"
        "Erfinde keine Ursachen und keine zusätzlichen Beobachtungen. "
        "Aus den Kennzahlen allein lassen sich keine Ursachen oder zeitlichen Verläufe ableiten.\n"
        "Kennzahlen (JSON):\n"
        + json.dumps(facts, ensure_ascii=False, allow_nan=False)
    )

    # The function is passed as a value; this is its only invocation.
    response = text_generator(prompt)
    if not isinstance(response, str) or not response.strip():
        raise ValueError("The text generator must return a nonempty text response.")
    return response
