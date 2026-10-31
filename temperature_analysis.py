"""Calculate deterministic temperature statistics using the standard library."""

import math
import statistics


def _validate_finite_number(value: int | float, name: str) -> None:
    """Raise ValueError unless value is a finite int or float, excluding bool."""
    # bool is a subclass of int, so it needs an explicit rejection.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite int or float, not a boolean.")

    # Integers are always finite. Check floats for NaN and both infinities.
    # Avoid converting integers to float merely for validation.
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")


def analyze_temperatures(
    values: list[int | float | None], threshold: int | float = 60.0
) -> dict[str, int | float]:
    """Return counts, extrema, mean, and strict threshold exceedances.

    values must be a list containing finite ints, finite floats, or None.
    None represents a missing measurement: it contributes to total_count
    and missing_count, but never to the calculations. No values are replaced
    and the input list is not modified.

    threshold must also be a finite int or float. Booleans are not accepted
    as measurements or as the threshold. Invalid inputs and lists without
    valid measurements raise ValueError. If the mean cannot be represented
    because its calculation overflows, ValueError is raised with the original
    OverflowError preserved as its cause.

    Results are not explicitly rounded; floating-point arithmetic still has
    its usual finite precision. Only values strictly above threshold count
    as exceedances.
    """
    # Type annotations describe expected inputs; runtime checks enforce them.
    if not isinstance(values, list):
        raise ValueError("values must be a list.")
    _validate_finite_number(threshold, "threshold")

    valid_values: list[int | float] = []
    missing_count = 0
    exceedance_count = 0

    for index, value in enumerate(values):
        if value is None:
            missing_count += 1
            continue

        # Reject invalid measurements instead of silently treating them as missing.
        _validate_finite_number(value, f"values[{index}]")
        valid_values.append(value)
        if value > threshold:
            exceedance_count += 1

    if not valid_values:
        raise ValueError("At least one valid measurement is required.")

    # All calculations use only validated measurements, without replacement
    # values or rounding. statistics.mean calculates the arithmetic mean.
    minimum = min(valid_values)
    maximum = max(valid_values)
    try:
        mean = statistics.mean(valid_values)
    except OverflowError as error:
        # Finite integers can still produce a mean too large for a float.
        raise ValueError(
            "The mean cannot be represented because it exceeds the numeric range."
        ) from error

    return {
        "total_count": len(values),
        "valid_count": len(valid_values),
        "missing_count": missing_count,
        "minimum": minimum,
        "maximum": maximum,
        "mean": mean,
        "exceedance_count": exceedance_count,
    }
