"""Read and validate temperature measurements without calculating statistics."""

import csv
import math
from pathlib import Path


def _parse_finite_number(text: str, line_number: int, field: str) -> float:
    """Convert a required numeric field, reporting its location on failure."""
    if not text.strip():
        raise ValueError(f"Line {line_number}, field {field}: a number is required.")

    try:
        value = float(text)
    except ValueError as error:
        raise ValueError(
            f"Line {line_number}, field {field}: expected a number."
        ) from error

    if not math.isfinite(value):
        raise ValueError(f"Line {line_number}, field {field}: number must be finite.")
    return value


def read_temperature_csv(path: str | Path) -> list[dict[str, float | None]]:
    """Read UTF-8 CSV with time_s and temperature_c columns, in that order.

    Each physical line must contain one CSV record with exactly two fields.
    Timestamps must be finite and strictly increasing. Temperatures must be
    finite or blank; blank temperatures become None without dropping rows.
    A file containing only missing temperatures is valid input for import.

    Return records in file order, with numbers converted to float. Format
    and content errors raise ValueError with a line number and, where
    applicable, a field name. File-system errors propagate unchanged.
    """
    records: list[dict[str, float | None]] = []
    previous_time: float | None = None
    line_number = 0

    # Decode individual lines so a UTF-8 error can name its exact line.
    # Binary iteration supports LF and CRLF endings; csv handles their text.
    with Path(path).open("rb") as source:
        for line_number, raw_line in enumerate(source, start=1):
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(f"Line {line_number}: invalid UTF-8 text.") from error

            try:
                # strict=True rejects malformed quoting instead of repairing it.
                row = next(csv.reader([line], delimiter=",", strict=True))
            except csv.Error as error:
                raise ValueError(
                    f"Line {line_number}: invalid CSV format ({error})."
                ) from error

            if line_number == 1:
                if row != ["time_s", "temperature_c"]:
                    raise ValueError(
                        "Line 1: expected header time_s,temperature_c."
                    )
                continue

            if not row or all(not field.strip() for field in row):
                raise ValueError(f"Line {line_number}: empty data row is not allowed.")
            if len(row) != 2:
                raise ValueError(f"Line {line_number}: expected exactly two fields.")

            time_s = _parse_finite_number(row[0], line_number, "time_s")
            if previous_time is not None and time_s <= previous_time:
                raise ValueError(
                    f"Line {line_number}, field time_s: timestamps must be "
                    "strictly increasing."
                )

            temperature_c = None
            if row[1].strip():
                temperature_c = _parse_finite_number(
                    row[1], line_number, "temperature_c"
                )

            # Keep every timestamp, including those with missing temperatures.
            records.append({"time_s": time_s, "temperature_c": temperature_c})
            previous_time = time_s

    if line_number == 0:
        raise ValueError("Line 1: file is empty; expected header time_s,temperature_c.")
    if not records:
        raise ValueError("Line 2: expected at least one data row after the header.")
    return records
