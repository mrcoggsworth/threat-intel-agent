# Analyst audit record

Record one secret-free JSON object per action in `events.jsonl` with:
`profile`, `job_or_session_id`, `action`, `repository_commit`, `service_run_id`,
`tool_result`, `approval_reference`, `deployment_record`, `error`, and
`rollback_result`. Redact tokens, cookies, authorization headers, database
URLs, private keys, and response bodies containing secrets. The analyst may
request publication but has no deployment authority.
