-- Show CSV/analysis evidence for all plain CLI runs in one database.
SELECT r.run_id, r.status, i.logical_name AS csv,
       json_extract(r.settings_json, '$.threshold') AS threshold,
       json_extract(a.content_text, '$.mean') AS mean,
       json_extract(a.content_text, '$.exceedance_count') AS exceedance_count
FROM runs AS r
JOIN artifacts AS i ON i.run_id = r.run_id AND i.kind = 'input_file'
JOIN artifacts AS a ON a.run_id = r.run_id AND a.kind = 'analysis'
    AND a.source_artifact_id = i.artifact_id
WHERE r.task_type = 'temperature_analysis'
ORDER BY r.started_at, r.run_id;
