CREATE TABLE IF NOT EXISTS gk_tasks (
    task_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    duration_ms INTEGER NULL,
    prompt TEXT NOT NULL,
    reasoning BOOLEAN NOT NULL,
    execution_mode TEXT NOT NULL,
    dry_run BOOLEAN NOT NULL DEFAULT TRUE,
    model_count INTEGER NOT NULL DEFAULT 1,
    quorum INTEGER NOT NULL DEFAULT 1,
    merge_strategy TEXT NOT NULL DEFAULT 'first_success',
    adapter_hint TEXT NOT NULL DEFAULT 'auto',
    cancel_on_quorum BOOLEAN NOT NULL DEFAULT TRUE,
    failure_code TEXT NULL,
    failure_message TEXT NULL,
    output_text TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS gk_task_steps (
    task_id TEXT NOT NULL REFERENCES gk_tasks(task_id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    model_display_name TEXT NOT NULL,
    backend TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    failure_code TEXT NULL,
    failure_message TEXT NULL,
    output_text TEXT NULL,
    duration_ms INTEGER NULL,
    PRIMARY KEY (task_id, step_index)
);

CREATE INDEX IF NOT EXISTS idx_gk_task_steps_model_id
ON gk_task_steps(model_id);

CREATE INDEX IF NOT EXISTS idx_gk_task_steps_status
ON gk_task_steps(status);

CREATE INDEX IF NOT EXISTS idx_gk_task_steps_provider
ON gk_task_steps(provider);

CREATE TABLE IF NOT EXISTS gk_task_events (
    event_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES gk_tasks(task_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (task_id, sequence_no)
);
