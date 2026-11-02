"""Choose report filenames and write approved text without terminal interaction."""

from pathlib import Path
from uuid import uuid4


def new_report_path() -> Path:
    """Choose a UUID filename under reports without creating any directory or file."""
    return Path("reports") / f"{uuid4()}.txt"


def write_report(path: Path, report: str) -> None:
    """Write the approved text exactly as UTF-8 and close before returning.

    The caller must obtain approval for this path and text before calling.
    Exclusive creation protects existing files, including on UUID collisions.
    Filesystem and encoding errors propagate. A write or close failure may leave
    a partial file; this function does not claim transactional or crash-safe storage.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(report)
