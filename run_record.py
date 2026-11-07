"""Carry completed run data between orchestration and a storage implementation."""

from dataclasses import dataclass
from pathlib import Path

from openai_text import OpenAITextResult


@dataclass(frozen=True)
class AnalysisRun:
    """Carry a successful CSV/analysis run without model or database objects.

    run_id may also identify the JSONL log. UTC times use microseconds; duration
    measures processing before database storage, not the database transaction.
    """

    run_id: str
    input_path: Path
    input_bytes: bytes
    analysis: dict[str, int | float]
    threshold: float
    started_at: str
    finished_at: str
    duration_ms: float


@dataclass(frozen=True)
class CompletedRun:
    """Describe one successful simulated run without database-specific fields.

    Times are UTC strings with microseconds. Run duration is locally measured;
    model_result.duration_ms belongs to the explicitly simulated model result.
    The input bytes supply the fingerprint of the referenced CSV, not an export.
    """

    input_path: Path
    input_bytes: bytes
    analysis: dict[str, int | float]
    threshold: float
    prompt: str
    model_result: OpenAITextResult
    report: str
    started_at: str
    finished_at: str
    duration_ms: float
    model_started_at: str
    model_finished_at: str
