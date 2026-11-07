-- Cosi-Lab database design v0.1 / schema version 1.
-- DESIGN ONLY: execute against a new, empty database.
-- Requires SQLite >= 3.38 with JSON support. No API requests or file exports.
-- Enable foreign keys on EVERY connection, before beginning a transaction.
PRAGMA foreign_keys = ON;
-- Also make DELETE guards apply to the implicit deletes of INSERT OR REPLACE.
PRAGMA recursive_triggers = ON;

BEGIN;

CREATE TABLE experiments (
    experiment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT NOT NULL,
    protocol_json TEXT NOT NULL CHECK (
        CASE WHEN json_valid(protocol_json) THEN json_type(protocol_json) = 'object' ELSE 0 END
    ),
    created_at TEXT NOT NULL CHECK (length(created_at) = 27 AND substr(created_at, 27) = 'Z')
) STRICT;

CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    experiment_id TEXT REFERENCES experiments(experiment_id) ON DELETE RESTRICT,
    case_id TEXT,
    variant TEXT,
    repetition INTEGER CHECK (repetition >= 1),
    task_type TEXT NOT NULL CHECK (length(trim(task_type)) > 0),
    execution_mode TEXT NOT NULL CHECK (execution_mode IN ('fixed', 'agent')),
    code_commit TEXT CHECK (code_commit IS NULL OR (
        length(code_commit) = 40 AND code_commit NOT GLOB '*[^0-9a-f]*'
    )),
    code_dirty INTEGER CHECK (code_dirty IN (0, 1)),
    settings_json TEXT NOT NULL CHECK (
        CASE WHEN json_valid(settings_json) THEN json_type(settings_json) = 'object' ELSE 0 END
    ),
    started_at TEXT NOT NULL CHECK (length(started_at) = 27 AND substr(started_at, 27) = 'Z'),
    finished_at TEXT CHECK (finished_at IS NULL OR (
        length(finished_at) = 27 AND substr(finished_at, 27) = 'Z'
    )),
    duration_ms REAL CHECK (duration_ms >= 0 AND duration_ms < 1.0e308),
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'cancelled', 'interrupted')),
    error_code TEXT CHECK (error_code IS NULL OR length(trim(error_code)) > 0),
    UNIQUE (experiment_id, case_id, variant, repetition),
    CHECK ((case_id IS NULL AND variant IS NULL AND repetition IS NULL) OR (
        experiment_id IS NOT NULL AND case_id IS NOT NULL
        AND variant IS NOT NULL AND repetition IS NOT NULL
    )),
    CHECK ((status = 'running' AND finished_at IS NULL AND duration_ms IS NULL AND error_code IS NULL)
        OR (status = 'succeeded' AND finished_at IS NOT NULL AND duration_ms IS NOT NULL AND error_code IS NULL)
        OR (status IN ('failed', 'cancelled', 'interrupted') AND finished_at IS NOT NULL AND error_code IS NOT NULL))
) STRICT;

-- Forward references are intentional: artifacts and calls belong to one run.
CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE RESTRICT,
    kind TEXT NOT NULL CHECK (kind IN ('input_file', 'analysis', 'report')),
    logical_name TEXT NOT NULL CHECK (length(trim(logical_name)) > 0),
    version INTEGER NOT NULL CHECK (version >= 1),
    source_artifact_id TEXT,
    model_call_id TEXT,
    media_type TEXT NOT NULL CHECK (length(trim(media_type)) > 0),
    content_text TEXT,
    file_path TEXT CHECK (file_path IS NULL OR length(trim(file_path)) > 0),
    content_sha256 TEXT NOT NULL CHECK (
        length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    created_at TEXT NOT NULL CHECK (length(created_at) = 27 AND substr(created_at, 27) = 'Z'),
    UNIQUE (artifact_id, run_id),
    UNIQUE (artifact_id, run_id, content_sha256),
    UNIQUE (run_id, kind, logical_name, version),
    FOREIGN KEY (source_artifact_id, run_id) REFERENCES artifacts(artifact_id, run_id) ON DELETE RESTRICT,
    FOREIGN KEY (model_call_id, run_id) REFERENCES model_calls(call_id, run_id) ON DELETE RESTRICT,
    CHECK (source_artifact_id IS NULL OR source_artifact_id <> artifact_id),
    CHECK ((kind = 'input_file' AND file_path IS NOT NULL AND content_text IS NULL
            AND source_artifact_id IS NULL AND model_call_id IS NULL)
        OR (kind = 'analysis' AND file_path IS NULL AND source_artifact_id IS NOT NULL
            AND model_call_id IS NULL AND content_text IS NOT NULL
            AND CASE WHEN json_valid(content_text) THEN json_type(content_text) = 'object' ELSE 0 END)
        OR (kind = 'report' AND file_path IS NULL AND source_artifact_id IS NOT NULL
            AND content_text IS NOT NULL AND length(trim(content_text)) > 0))
) STRICT;

CREATE TABLE model_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE RESTRICT,
    call_index INTEGER NOT NULL CHECK (call_index >= 1),
    input_artifact_id TEXT NOT NULL,
    provider TEXT NOT NULL CHECK (length(trim(provider)) > 0),
    model_requested TEXT NOT NULL CHECK (length(trim(model_requested)) > 0),
    model_returned TEXT,
    prompt_text TEXT NOT NULL CHECK (length(trim(prompt_text)) > 0),
    prompt_sha256 TEXT NOT NULL CHECK (
        length(prompt_sha256) = 64 AND prompt_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    request_json TEXT NOT NULL CHECK (
        CASE WHEN json_valid(request_json) THEN json_type(request_json) = 'object' ELSE 0 END
    ),
    started_at TEXT NOT NULL CHECK (length(started_at) = 27 AND substr(started_at, 27) = 'Z'),
    finished_at TEXT CHECK (finished_at IS NULL OR (
        length(finished_at) = 27 AND substr(finished_at, 27) = 'Z'
    )),
    duration_ms REAL CHECK (duration_ms >= 0 AND duration_ms < 1.0e308),
    status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed', 'interrupted')),
    http_status INTEGER CHECK (http_status BETWEEN 100 AND 599),
    response_status TEXT,
    response_id TEXT,
    request_id TEXT,
    response_text TEXT,
    -- Retain valid UTF-8 JSON from HTTP 2xx responses without reformatting it.
    -- Do not store raw non-2xx error bodies. Store safe error codes below.
    response_json TEXT CHECK (response_json IS NULL OR json_valid(response_json)),
    response_headers_json TEXT NOT NULL DEFAULT '{}' CHECK (
        CASE WHEN json_valid(response_headers_json) THEN json_type(response_headers_json) = 'object' ELSE 0 END
    ),
    server_processing_ms REAL CHECK (server_processing_ms >= 0 AND server_processing_ms < 1.0e308),
    provider_created_at INTEGER CHECK (provider_created_at >= 0),
    provider_completed_at INTEGER CHECK (provider_completed_at >= 0),
    input_tokens INTEGER CHECK (input_tokens >= 0),
    output_tokens INTEGER CHECK (output_tokens >= 0),
    total_tokens INTEGER CHECK (total_tokens >= 0),
    cached_input_tokens INTEGER CHECK (cached_input_tokens >= 0),
    reasoning_output_tokens INTEGER CHECK (reasoning_output_tokens >= 0),
    usage_json TEXT CHECK (usage_json IS NULL OR (
        CASE WHEN json_valid(usage_json) THEN json_type(usage_json) = 'object' ELSE 0 END
    )),
    error_code TEXT CHECK (error_code IS NULL OR length(trim(error_code)) > 0),
    provider_error_code TEXT,
    provider_error_type TEXT,
    UNIQUE (call_id, run_id),
    UNIQUE (run_id, call_index),
    FOREIGN KEY (input_artifact_id, run_id) REFERENCES artifacts(artifact_id, run_id) ON DELETE RESTRICT,
    CHECK ((status = 'started' AND finished_at IS NULL AND duration_ms IS NULL
            AND error_code IS NULL AND response_text IS NULL)
        OR (status = 'succeeded' AND finished_at IS NOT NULL AND duration_ms IS NOT NULL
            AND response_text IS NOT NULL AND length(trim(response_text)) > 0
            AND error_code IS NULL AND provider_error_code IS NULL AND provider_error_type IS NULL)
        OR (status IN ('failed', 'interrupted') AND finished_at IS NOT NULL AND error_code IS NOT NULL)),
    CHECK (status <> 'succeeded' OR http_status IS NULL OR http_status BETWEEN 200 AND 299),
    CHECK (response_json IS NULL OR http_status IS NULL OR http_status BETWEEN 200 AND 299),
    CHECK (total_tokens IS NULL OR input_tokens IS NULL OR output_tokens IS NULL
        OR total_tokens = input_tokens + output_tokens),
    CHECK (cached_input_tokens IS NULL OR input_tokens IS NULL OR cached_input_tokens <= input_tokens),
    CHECK (reasoning_output_tokens IS NULL OR output_tokens IS NULL OR reasoning_output_tokens <= output_tokens)
) STRICT;

CREATE TABLE approvals (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE RESTRICT,
    artifact_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action = 'export_report'),
    target_path TEXT NOT NULL CHECK (length(trim(target_path)) > 0),
    content_sha256 TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'declined')),
    reason_code TEXT NOT NULL CHECK (reason_code IN ('explicit_yes', 'not_approved', 'eof', 'interrupted')),
    actor TEXT NOT NULL CHECK (length(trim(actor)) > 0),
    decided_at TEXT NOT NULL CHECK (length(decided_at) = 27 AND substr(decided_at, 27) = 'Z'),
    UNIQUE (approval_id, run_id, artifact_id, target_path, content_sha256, decision),
    FOREIGN KEY (artifact_id, run_id, content_sha256)
        REFERENCES artifacts(artifact_id, run_id, content_sha256) ON DELETE RESTRICT,
    CHECK ((decision = 'approved' AND reason_code = 'explicit_yes')
        OR (decision = 'declined' AND reason_code <> 'explicit_yes'))
) STRICT;

CREATE TABLE exports (
    export_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE RESTRICT,
    artifact_id TEXT NOT NULL,
    approval_id TEXT NOT NULL UNIQUE,
    target_path TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    -- This constant makes the foreign key require an APPROVED decision.
    approval_decision TEXT NOT NULL DEFAULT 'approved' CHECK (approval_decision = 'approved'),
    started_at TEXT NOT NULL CHECK (length(started_at) = 27 AND substr(started_at, 27) = 'Z'),
    finished_at TEXT CHECK (finished_at IS NULL OR (
        length(finished_at) = 27 AND substr(finished_at, 27) = 'Z'
    )),
    duration_ms REAL CHECK (duration_ms >= 0 AND duration_ms < 1.0e308),
    status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed', 'interrupted')),
    file_state TEXT NOT NULL CHECK (file_state IN ('unknown', 'absent', 'partial', 'complete')),
    written_bytes INTEGER CHECK (written_bytes >= 0),
    error_code TEXT CHECK (error_code IS NULL OR length(trim(error_code)) > 0),
    UNIQUE (export_id, run_id),
    FOREIGN KEY (approval_id, run_id, artifact_id, target_path, content_sha256, approval_decision)
        REFERENCES approvals(approval_id, run_id, artifact_id, target_path, content_sha256, decision)
        ON DELETE RESTRICT,
    CHECK ((status = 'started' AND finished_at IS NULL AND duration_ms IS NULL AND error_code IS NULL)
        OR (status = 'succeeded' AND finished_at IS NOT NULL AND duration_ms IS NOT NULL
            AND file_state = 'complete' AND written_bytes IS NOT NULL AND error_code IS NULL)
        OR (status IN ('failed', 'interrupted') AND finished_at IS NOT NULL AND error_code IS NOT NULL))
) STRICT;

CREATE TABLE run_events (
    event_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE RESTRICT,
    sequence_no INTEGER NOT NULL CHECK (sequence_no >= 1),
    occurred_at TEXT NOT NULL CHECK (length(occurred_at) = 27 AND substr(occurred_at, 27) = 'Z'),
    event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
    step_name TEXT,
    model_call_id TEXT,
    artifact_id TEXT,
    export_id TEXT,
    duration_ms REAL CHECK (duration_ms >= 0 AND duration_ms < 1.0e308),
    error_type TEXT,
    details_json TEXT NOT NULL DEFAULT '{}' CHECK (
        CASE WHEN json_valid(details_json) THEN json_type(details_json) = 'object' ELSE 0 END
    ),
    UNIQUE (run_id, sequence_no),
    FOREIGN KEY (model_call_id, run_id) REFERENCES model_calls(call_id, run_id) ON DELETE RESTRICT,
    FOREIGN KEY (artifact_id, run_id) REFERENCES artifacts(artifact_id, run_id) ON DELETE RESTRICT,
    FOREIGN KEY (export_id, run_id) REFERENCES exports(export_id, run_id) ON DELETE RESTRICT
) STRICT;

CREATE TABLE evaluations (
    evaluation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE RESTRICT,
    artifact_id TEXT,
    model_call_id TEXT,
    criterion TEXT NOT NULL CHECK (length(trim(criterion)) > 0),
    criterion_version TEXT NOT NULL CHECK (length(trim(criterion_version)) > 0),
    verdict TEXT NOT NULL CHECK (verdict IN ('passed', 'failed', 'unclear', 'not_applicable')),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
    evaluator TEXT NOT NULL CHECK (length(trim(evaluator)) > 0),
    created_at TEXT NOT NULL CHECK (length(created_at) = 27 AND substr(created_at, 27) = 'Z'),
    FOREIGN KEY (artifact_id, run_id) REFERENCES artifacts(artifact_id, run_id) ON DELETE RESTRICT,
    FOREIGN KEY (model_call_id, run_id) REFERENCES model_calls(call_id, run_id) ON DELETE RESTRICT,
    CHECK ((artifact_id IS NOT NULL AND model_call_id IS NULL)
        OR (artifact_id IS NULL AND model_call_id IS NOT NULL))
) STRICT;

-- Index foreign-key lookups and our first concrete diagnostic queries.
CREATE INDEX runs_status_time ON runs(status, started_at);
CREATE INDEX artifacts_source ON artifacts(source_artifact_id, run_id);
CREATE INDEX artifacts_model_call ON artifacts(model_call_id, run_id);
CREATE INDEX calls_input ON model_calls(input_artifact_id, run_id);
CREATE INDEX calls_diagnostics ON model_calls(status, http_status, error_code);
CREATE INDEX approvals_artifact ON approvals(artifact_id, run_id, content_sha256);
CREATE INDEX exports_artifact ON exports(artifact_id, run_id);
CREATE INDEX events_call ON run_events(model_call_id, run_id);
CREATE INDEX events_artifact ON run_events(artifact_id, run_id);
CREATE INDEX events_export ON run_events(export_id, run_id);
CREATE INDEX evaluations_artifact ON evaluations(artifact_id, run_id, criterion);
CREATE INDEX evaluations_call ON evaluations(model_call_id, run_id, criterion);

-- Foreign keys ensure existence and run ownership; these guards add kind rules.
CREATE TRIGGER artifacts_validate_source BEFORE INSERT ON artifacts
BEGIN
    SELECT CASE
        WHEN NEW.kind = 'analysis' AND NOT EXISTS (
            SELECT 1 FROM artifacts WHERE artifact_id = NEW.source_artifact_id
                AND run_id = NEW.run_id AND kind = 'input_file'
        ) THEN RAISE(ABORT, 'analysis requires an input-file source')
        WHEN NEW.kind = 'report' AND NOT EXISTS (
            SELECT 1 FROM artifacts WHERE artifact_id = NEW.source_artifact_id
                AND run_id = NEW.run_id AND kind = 'analysis'
        ) THEN RAISE(ABORT, 'report requires an analysis source')
        WHEN NEW.model_call_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM model_calls WHERE call_id = NEW.model_call_id
                AND run_id = NEW.run_id AND status = 'succeeded'
                AND input_artifact_id = NEW.source_artifact_id
        ) THEN RAISE(ABORT, 'report requires a successful call for its analysis')
    END;
END;

CREATE TRIGGER calls_validate_input BEFORE INSERT ON model_calls
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM artifacts WHERE artifact_id = NEW.input_artifact_id
            AND run_id = NEW.run_id AND kind = 'analysis'
    ) THEN RAISE(ABORT, 'model call requires an analysis artifact') END;
END;

CREATE TRIGGER approvals_validate_kind BEFORE INSERT ON approvals
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM artifacts WHERE artifact_id = NEW.artifact_id
            AND run_id = NEW.run_id AND kind = 'report'
    ) THEN RAISE(ABORT, 'only report artifacts can be approved for export') END;
END;

CREATE TRIGGER exports_validate_size_insert BEFORE INSERT ON exports
WHEN NEW.status = 'succeeded'
BEGIN
    SELECT CASE WHEN NEW.written_bytes <> (
        SELECT byte_count FROM artifacts WHERE artifact_id = NEW.artifact_id AND run_id = NEW.run_id
    ) THEN RAISE(ABORT, 'successful export must have the expected byte count') END;
END;

CREATE TRIGGER exports_validate_size_update BEFORE UPDATE ON exports
WHEN NEW.status = 'succeeded'
BEGIN
    SELECT CASE WHEN NEW.written_bytes <> (
        SELECT byte_count FROM artifacts WHERE artifact_id = NEW.artifact_id AND run_id = NEW.run_id
    ) THEN RAISE(ABORT, 'successful export must have the expected byte count') END;
END;

-- Evidence rows are append-only; lifecycle rows can be finalized once.

CREATE TRIGGER experiments_deny_update BEFORE UPDATE ON experiments
BEGIN
    SELECT RAISE(ABORT, 'experiments rows are immutable');
END;

CREATE TRIGGER experiments_deny_delete BEFORE DELETE ON experiments
BEGIN
    SELECT RAISE(ABORT, 'experiments rows are immutable');
END;

CREATE TRIGGER artifacts_deny_update BEFORE UPDATE ON artifacts
BEGIN
    SELECT RAISE(ABORT, 'artifacts rows are immutable');
END;

CREATE TRIGGER artifacts_deny_delete BEFORE DELETE ON artifacts
BEGIN
    SELECT RAISE(ABORT, 'artifacts rows are immutable');
END;

CREATE TRIGGER approvals_deny_update BEFORE UPDATE ON approvals
BEGIN
    SELECT RAISE(ABORT, 'approvals rows are immutable');
END;

CREATE TRIGGER approvals_deny_delete BEFORE DELETE ON approvals
BEGIN
    SELECT RAISE(ABORT, 'approvals rows are immutable');
END;

CREATE TRIGGER run_events_deny_update BEFORE UPDATE ON run_events
BEGIN
    SELECT RAISE(ABORT, 'run_events rows are immutable');
END;

CREATE TRIGGER run_events_deny_delete BEFORE DELETE ON run_events
BEGIN
    SELECT RAISE(ABORT, 'run_events rows are immutable');
END;

CREATE TRIGGER evaluations_deny_update BEFORE UPDATE ON evaluations
BEGIN
    SELECT RAISE(ABORT, 'evaluations rows are immutable');
END;

CREATE TRIGGER evaluations_deny_delete BEFORE DELETE ON evaluations
BEGIN
    SELECT RAISE(ABORT, 'evaluations rows are immutable');
END;

CREATE TRIGGER runs_deny_delete BEFORE DELETE ON runs
BEGIN
    SELECT RAISE(ABORT, 'runs rows cannot be deleted');
END;

CREATE TRIGGER runs_guard_update BEFORE UPDATE ON runs
WHEN OLD.status <> 'running'
    OR NEW.run_id IS NOT OLD.run_id
    OR NEW.experiment_id IS NOT OLD.experiment_id
    OR NEW.case_id IS NOT OLD.case_id
    OR NEW.variant IS NOT OLD.variant
    OR NEW.repetition IS NOT OLD.repetition
    OR NEW.task_type IS NOT OLD.task_type
    OR NEW.execution_mode IS NOT OLD.execution_mode
    OR NEW.code_commit IS NOT OLD.code_commit
    OR NEW.code_dirty IS NOT OLD.code_dirty
    OR NEW.settings_json IS NOT OLD.settings_json
    OR NEW.started_at IS NOT OLD.started_at
BEGIN
    SELECT RAISE(ABORT, 'runs identity and finalized records are immutable');
END;

CREATE TRIGGER model_calls_deny_delete BEFORE DELETE ON model_calls
BEGIN
    SELECT RAISE(ABORT, 'model_calls rows cannot be deleted');
END;

CREATE TRIGGER model_calls_guard_update BEFORE UPDATE ON model_calls
WHEN OLD.status <> 'started'
    OR NEW.call_id IS NOT OLD.call_id
    OR NEW.run_id IS NOT OLD.run_id
    OR NEW.call_index IS NOT OLD.call_index
    OR NEW.input_artifact_id IS NOT OLD.input_artifact_id
    OR NEW.provider IS NOT OLD.provider
    OR NEW.model_requested IS NOT OLD.model_requested
    OR NEW.prompt_text IS NOT OLD.prompt_text
    OR NEW.prompt_sha256 IS NOT OLD.prompt_sha256
    OR NEW.request_json IS NOT OLD.request_json
    OR NEW.started_at IS NOT OLD.started_at
BEGIN
    SELECT RAISE(ABORT, 'model_calls identity and finalized records are immutable');
END;

CREATE TRIGGER exports_deny_delete BEFORE DELETE ON exports
BEGIN
    SELECT RAISE(ABORT, 'exports rows cannot be deleted');
END;

CREATE TRIGGER exports_guard_update BEFORE UPDATE ON exports
WHEN OLD.status <> 'started'
    OR NEW.export_id IS NOT OLD.export_id
    OR NEW.run_id IS NOT OLD.run_id
    OR NEW.artifact_id IS NOT OLD.artifact_id
    OR NEW.approval_id IS NOT OLD.approval_id
    OR NEW.target_path IS NOT OLD.target_path
    OR NEW.content_sha256 IS NOT OLD.content_sha256
    OR NEW.approval_decision IS NOT OLD.approval_decision
    OR NEW.started_at IS NOT OLD.started_at
BEGIN
    SELECT RAISE(ABORT, 'exports identity and finalized records are immutable');
END;

PRAGMA application_id = 1129272137;
PRAGMA user_version = 1;
COMMIT;
