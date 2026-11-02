"""Write technical run metadata as UTF-8 JSONL, without input contents."""

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class RunLoggingError(Exception):
    """Distinguish logging failures from errors in the processing steps."""


class RunLogger:
    """Own one exclusively created log file and serialize metadata events."""

    def __init__(self, log_dir: str | Path) -> None:
        """Create the directory if needed; never overwrite an existing log."""
        self.run_id = str(uuid4())
        try:
            directory = Path(log_dir)
            directory.mkdir(parents=True, exist_ok=True)
            self._stream = open(
                directory / f"{self.run_id}.jsonl", "x", encoding="utf-8", newline="\n"
            )
        except (OSError, ValueError) as error:
            raise RunLoggingError("Protokolldatei konnte nicht angelegt werden.") from error

    def write_event(
        self,
        event: str,
        step: str | None,
        status: str,
        duration_ms: float | None = None,
        error_type: str | None = None,
    ) -> None:
        """Write and flush one complete JSON line containing only fixed fields."""
        record = {
            "schema_version": 1,
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "step": step,
            "status": status,
            "duration_ms": duration_ms,
            "error_type": error_type,
        }
        line = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
        try:
            self._stream.write(line)
            # Detect buffered write failures before advancing to the next step.
            self._stream.flush()
        except (OSError, ValueError) as error:
            raise RunLoggingError("Protokollereignis konnte nicht geschrieben werden.") from error

    def close(self) -> None:
        """Close the file, surfacing errors before the CLI reports success."""
        try:
            self._stream.close()
        except (OSError, ValueError) as error:
            raise RunLoggingError("Protokolldatei konnte nicht geschlossen werden.") from error


@contextmanager
def log_run(log_dir: str | Path | None) -> Iterator[RunLogger | None]:
    """Bracket a run with events and close its file even if an operation fails.

    With no directory, yield None without creating files or identifiers.
    contextmanager lets the caller use a with block: code before yield opens
    the run, and code after yield handles its completion. finally always closes
    an opened file, including when writing run_started fails.
    Record processing exceptions without provider-specific imports and re-raise
    them unchanged. Logging failures propagate without further write attempts.
    """
    if log_dir is None:
        yield None
        return

    logger = RunLogger(log_dir)
    try:
        started = time.perf_counter()
        logger.write_event("run_started", None, "started")
        try:
            yield logger
        except RunLoggingError:
            raise
        except Exception as error:
            # Observe processing failures without handling or converting them.
            duration_ms = (time.perf_counter() - started) * 1000
            logger.write_event("run_finished", None, "error", duration_ms, type(error).__name__)
            raise
        else:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.write_event("run_finished", None, "success", duration_ms)
    finally:
        logger.close()


@contextmanager
def log_step(logger: RunLogger | None, step: str) -> Iterator[None]:
    """Record processing failures and preserve them; never retry a logging failure."""
    if logger is None:
        yield
        return

    # perf_counter measures elapsed time independently of wall-clock changes.
    started = time.perf_counter()
    logger.write_event("step_started", step, "started")
    try:
        yield
    except RunLoggingError:
        raise
    except Exception as error:
        # The caller decides which exceptions it can handle; logging only records.
        duration_ms = (time.perf_counter() - started) * 1000
        logger.write_event("step_finished", step, "error", duration_ms, type(error).__name__)
        raise
    else:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.write_event("step_finished", step, "success", duration_ms)
