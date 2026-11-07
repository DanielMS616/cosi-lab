-- Join the complete evidence chain after closing and reopening the database.
SELECT r.status, json_extract(r.settings_json, '$.simulation') AS simulation,
       i.file_path AS csv_path, i.byte_count AS csv_bytes,
       a.content_text AS analysis_json,
       m.provider, m.model_requested, m.model_returned,
       m.response_id, m.request_id,
       m.input_tokens, m.output_tokens, m.total_tokens, m.duration_ms,
       m.http_status, m.response_json,
       length(m.prompt_text) AS prompt_characters,
       b.content_text AS report,
       (m.response_text = b.content_text) AS report_matches_response
FROM runs AS r
JOIN artifacts AS i ON i.run_id = r.run_id AND i.kind = 'input_file'
JOIN artifacts AS a ON a.run_id = r.run_id
    AND a.source_artifact_id = i.artifact_id AND a.kind = 'analysis'
JOIN model_calls AS m ON m.run_id = r.run_id AND m.input_artifact_id = a.artifact_id
JOIN artifacts AS b ON b.run_id = r.run_id AND b.source_artifact_id = a.artifact_id
    AND b.model_call_id = m.call_id AND b.kind = 'report';
