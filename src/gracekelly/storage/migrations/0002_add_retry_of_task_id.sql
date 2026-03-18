ALTER TABLE gk_tasks ADD COLUMN IF NOT EXISTS retry_of_task_id TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_gk_tasks_retry_of ON gk_tasks (retry_of_task_id) WHERE retry_of_task_id IS NOT NULL;
