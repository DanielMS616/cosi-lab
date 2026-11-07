-- Include archived reports whose decision or export has not been confirmed.
SELECT r.run_id, r.status AS run_status, b.artifact_id AS report_id,
       b.content_sha256, b.byte_count, a.decision, a.reason_code, a.target_path,
       e.status AS export_status, e.file_state, e.written_bytes, e.error_code
FROM runs AS r
JOIN artifacts AS b ON b.run_id = r.run_id AND b.kind = 'report'
LEFT JOIN approvals AS a ON a.run_id = r.run_id AND a.artifact_id = b.artifact_id
    AND a.content_sha256 = b.content_sha256
LEFT JOIN exports AS e ON e.run_id = r.run_id AND e.approval_id = a.approval_id
    AND e.artifact_id = b.artifact_id AND e.target_path = a.target_path
    AND e.content_sha256 = b.content_sha256
ORDER BY r.started_at, r.run_id;
