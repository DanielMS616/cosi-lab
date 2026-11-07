-- LEFT JOIN retains failed or unconfirmed calls without a report artifact.
SELECT r.run_id, r.status AS run_status, m.status AS call_status,
       m.error_code, m.http_status, m.response_id, m.request_id,
       length(m.prompt_text) AS prompt_characters,
       (b.artifact_id IS NOT NULL) AS has_report
FROM runs AS r
JOIN model_calls AS m ON m.run_id = r.run_id
LEFT JOIN artifacts AS b ON b.run_id = r.run_id
    AND b.model_call_id = m.call_id AND b.kind = 'report'
WHERE r.task_type = 'temperature_report'
ORDER BY r.started_at, r.run_id;
