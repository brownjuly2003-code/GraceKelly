ALTER TABLE gk_tasks ADD COLUMN IF NOT EXISTS session_id TEXT;
CREATE INDEX IF NOT EXISTS idx_gk_tasks_session_id ON gk_tasks (session_id) WHERE session_id IS NOT NULL;
