"""Carry run evidence and summaries between orchestration and storage."""

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
class ModelCallReference:
    """Identify committed start evidence without holding a database connection."""

    run_id: str
    call_id: str
    analysis_id: str


@dataclass(frozen=True)
class ReportReference:
    """Bind approval to an immutable archived report and its UTF-8 fingerprint."""

    run_id: str
    artifact_id: str
    content_sha256: str
    byte_count: int


@dataclass(frozen=True)
class ApprovalDecision:
    """Carry a normalized terminal decision without retaining the raw input."""

    approved: bool
    reason_code: str


@dataclass(frozen=True)
class ExportReference:
    """Identify a committed export start for one report and concrete target."""

    run_id: str
    export_id: str
    artifact_id: str
    target_path: Path
    byte_count: int


@dataclass(frozen=True)
class RunSummary:
    """Carry overview metadata only, without prompts, responses or report text."""

    run_id: str
    started_at: str
    task_type: str
    status: str
    run_error_code: str | None
    model_status: str | None
    model_returned: str | None
    model_error_code: str | None
    http_status: int | None
    approval_status: str | None
    export_status: str | None
    export_error_code: str | None


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
