from __future__ import annotations

import json
import logging
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover
    psycopg = None
    dict_row = None

try:
    from psycopg_pool import ConnectionPool
except ModuleNotFoundError:  # pragma: no cover
    ConnectionPool = None

from gracekelly.core.contracts import AdapterHint, EventType, ExecutionMode, FailureCode, MergeStrategy, StepStatus, TaskStatus
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskRepository, TaskStepRecord
from gracekelly.storage.schema import (
    EXPECTED_SCHEMA_COLUMNS,
    INITIAL_MIGRATION_NAME,
    MIGRATION_TRACKING_DDL,
    compute_schema_diff,
    discover_migrations,
    load_migration_sql,
    split_sql_statements,
)

logger = logging.getLogger(__name__)

_TASK_UPSERT_QUERY = """
INSERT INTO gk_tasks (
    task_id,
    status,
    accepted_at,
    completed_at,
    duration_ms,
    prompt,
    reasoning,
    execution_mode,
    dry_run,
    model_count,
    quorum,
    merge_strategy,
    adapter_hint,
    cancel_on_quorum,
    failure_code,
    failure_message,
    output_text,
    metadata,
    retry_of_task_id
)
VALUES (
    %(task_id)s,
    %(status)s,
    %(accepted_at)s,
    %(completed_at)s,
    %(duration_ms)s,
    %(prompt)s,
    %(reasoning)s,
    %(execution_mode)s,
    %(dry_run)s,
    %(model_count)s,
    %(quorum)s,
    %(merge_strategy)s,
    %(adapter_hint)s,
    %(cancel_on_quorum)s,
    %(failure_code)s,
    %(failure_message)s,
    %(output_text)s,
    %(metadata)s::jsonb,
    %(retry_of_task_id)s
)
ON CONFLICT (task_id) DO UPDATE SET
    status = EXCLUDED.status,
    accepted_at = EXCLUDED.accepted_at,
    completed_at = EXCLUDED.completed_at,
    duration_ms = EXCLUDED.duration_ms,
    prompt = EXCLUDED.prompt,
    reasoning = EXCLUDED.reasoning,
    execution_mode = EXCLUDED.execution_mode,
    dry_run = EXCLUDED.dry_run,
    model_count = EXCLUDED.model_count,
    quorum = EXCLUDED.quorum,
    merge_strategy = EXCLUDED.merge_strategy,
    adapter_hint = EXCLUDED.adapter_hint,
    cancel_on_quorum = EXCLUDED.cancel_on_quorum,
    failure_code = EXCLUDED.failure_code,
    failure_message = EXCLUDED.failure_message,
    output_text = EXCLUDED.output_text,
    metadata = EXCLUDED.metadata,
    retry_of_task_id = EXCLUDED.retry_of_task_id;
"""

_STEP_UPSERT_QUERY = """
INSERT INTO gk_task_steps (
    task_id,
    step_index,
    model_id,
    model_display_name,
    backend,
    provider,
    status,
    failure_code,
    failure_message,
    output_text,
    duration_ms
)
VALUES (
    %(task_id)s,
    %(step_index)s,
    %(model_id)s,
    %(model_display_name)s,
    %(backend)s,
    %(provider)s,
    %(status)s,
    %(failure_code)s,
    %(failure_message)s,
    %(output_text)s,
    %(duration_ms)s
)
ON CONFLICT (task_id, step_index) DO UPDATE SET
    model_id = EXCLUDED.model_id,
    model_display_name = EXCLUDED.model_display_name,
    backend = EXCLUDED.backend,
    provider = EXCLUDED.provider,
    status = EXCLUDED.status,
    failure_code = EXCLUDED.failure_code,
    failure_message = EXCLUDED.failure_message,
    output_text = EXCLUDED.output_text,
    duration_ms = EXCLUDED.duration_ms;
"""

_EVENT_INSERT_QUERY = """
INSERT INTO gk_task_events (
    event_id,
    task_id,
    sequence_no,
    event_type,
    created_at,
    payload
)
VALUES (
    %(event_id)s,
    %(task_id)s,
    %(sequence_no)s,
    %(event_type)s,
    %(created_at)s,
    %(payload)s::jsonb
)
"""


class PostgresTaskRepository(TaskRepository):
    backend_name = "postgres"

    def __init__(
        self,
        dsn: str,
        *,
        bootstrap: bool = True,
        connect_timeout_seconds: int = 5,
        use_pool: bool = False,
        pool_min_size: int = 1,
        pool_max_size: int = 5,
    ) -> None:
        if psycopg is None:  # pragma: no cover
            raise RuntimeError("psycopg is required for the PostgreSQL backend.")
        self._dsn = dsn
        self._connect_timeout_seconds = connect_timeout_seconds
        self._pool: Any | None = None
        if use_pool:
            if ConnectionPool is None:  # pragma: no cover
                logger.warning("psycopg_pool is not installed, falling back to direct connections.")
            else:
                self._pool = ConnectionPool(
                    dsn,
                    min_size=pool_min_size,
                    max_size=pool_max_size,
                    kwargs={"connect_timeout": connect_timeout_seconds},
                )
                logger.info(
                    "postgres.pool.started min_size=%s max_size=%s",
                    pool_min_size,
                    pool_max_size,
                )
        if bootstrap:
            self.bootstrap()

    def bootstrap(self) -> None:
        logger.info(
            "postgres.bootstrap.started connect_timeout_seconds=%s",
            self._connect_timeout_seconds,
        )
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(MIGRATION_TRACKING_DDL)
                conn.commit()
                applied = self._applied_migrations(cursor)
                pending = [m for m in discover_migrations() if m not in applied]
                for migration_name in pending:
                    sql = load_migration_sql(migration_name)
                    for statement in split_sql_statements(sql):
                        cursor.execute(statement)
                    cursor.execute(
                        "INSERT INTO gk_schema_migrations (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (migration_name,),
                    )
                    conn.commit()
                    logger.info("postgres.migration.applied name=%s", migration_name)
        logger.info(
            "postgres.bootstrap.completed migrations_applied=%d",
            len(pending),
        )

    def applied_migrations(self) -> list[str]:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                return self._applied_migrations(cursor)

    @staticmethod
    def _applied_migrations(cursor: Any) -> set[str]:
        try:
            cursor.execute(
                "SELECT name FROM gk_schema_migrations ORDER BY name"
            )
            return {row[0] for row in cursor.fetchall()}
        except Exception:
            return set()

    def save_task_with_steps(
        self,
        task: TaskRecord,
        steps: list[TaskStepRecord],
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                self._save_task_with_steps_in_cursor(cursor, task, steps)
            conn.commit()

    def replace_task_snapshot(
        self,
        task: TaskRecord,
        steps: list[TaskStepRecord],
        events: list[TaskEventRecord],
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM gk_tasks WHERE task_id = %s", (task.task_id,))
                self._save_task_with_steps_in_cursor(cursor, task, steps)
                for event in events:
                    self._append_event_in_cursor(cursor, event)
            conn.commit()

    def get(self, task_id: str) -> TaskRecord | None:
        query = "SELECT * FROM gk_tasks WHERE task_id = %s"
        with self._connect(row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (task_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return self._task_from_row(row)

    def list_recent(
        self,
        limit: int,
        *,
        status: TaskStatus | None = None,
        execution_mode: ExecutionMode | None = None,
        dry_run: bool | None = None,
        failure_code: FailureCode | None = None,
    ) -> list[TaskRecord]:
        where_clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            where_clauses.append("status = %s")
            params.append(status)
        if execution_mode is not None:
            where_clauses.append("execution_mode = %s")
            params.append(execution_mode)
        if dry_run is not None:
            where_clauses.append("dry_run = %s")
            params.append(dry_run)
        if failure_code is not None:
            where_clauses.append("failure_code = %s")
            params.append(failure_code)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        query = f"""
        SELECT *
        FROM gk_tasks
        {where_sql}
        ORDER BY accepted_at DESC, task_id DESC
        LIMIT %s
        """
        params.append(limit)
        with self._connect(row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        return [self._task_from_row(row) for row in rows]

    def list_steps(self, task_id: str) -> list[TaskStepRecord]:
        query = """
        SELECT
            task_id,
            step_index,
            model_id,
            model_display_name,
            backend,
            provider,
            status,
            failure_code,
            failure_message,
            output_text,
            duration_ms
        FROM gk_task_steps
        WHERE task_id = %s
        ORDER BY step_index ASC
        """
        with self._connect(row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (task_id,))
                rows = cursor.fetchall()
        return [self._step_from_row(row) for row in rows]

    def append_event(self, event: TaskEventRecord) -> None:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                self._append_event_in_cursor(cursor, event)
            conn.commit()

    def list_events(self, task_id: str) -> list[TaskEventRecord]:
        query = """
        SELECT event_id, task_id, sequence_no, event_type, created_at, payload
        FROM gk_task_events
        WHERE task_id = %s
        ORDER BY sequence_no ASC
        """
        with self._connect(row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (task_id,))
                rows = cursor.fetchall()
        return [self._event_from_row(row) for row in rows]

    def healthcheck(self) -> dict[str, Any]:
        try:
            row = self._load_health_ping()
            counts = self._load_storage_counts()
            return {
                "status": "ok",
                "backend": self.backend_name,
                "schema_version": INITIAL_MIGRATION_NAME,
                "details": row or {"ok": 1},
                **counts,
            }
        except Exception as exc:
            logger.warning(
                "postgres.healthcheck.degraded schema_version=%s connect_timeout_seconds=%s error=%r",
                INITIAL_MIGRATION_NAME,
                self._connect_timeout_seconds,
                exc,
            )
            return {
                "status": "degraded",
                "backend": self.backend_name,
                "schema_version": INITIAL_MIGRATION_NAME,
                "error": str(exc),
            }

    def schema_report(self) -> dict[str, Any]:
        try:
            actual_columns = self._load_schema_columns()
            diff = compute_schema_diff(actual_columns)
            missing_tables = diff["missing_tables"]
            missing_columns = diff["missing_columns"]
            if missing_tables or missing_columns:
                logger.warning(
                    "postgres.schema_report.degraded schema_version=%s missing_tables=%s missing_column_tables=%s",
                    INITIAL_MIGRATION_NAME,
                    len(missing_tables),
                    len(missing_columns),
                )
            available = discover_migrations()
            try:
                applied = self.applied_migrations()
            except Exception:
                applied = []
            pending = [m for m in available if m not in set(applied)]
            return {
                "status": "ok" if not missing_tables and not missing_columns else "degraded",
                "backend": self.backend_name,
                "schema_version": INITIAL_MIGRATION_NAME,
                "expected_tables": sorted(EXPECTED_SCHEMA_COLUMNS),
                "missing_tables": missing_tables,
                "missing_columns": missing_columns,
                "migrations_available": available,
                "migrations_applied": applied,
                "migrations_pending": pending,
            }
        except Exception as exc:
            logger.warning(
                "postgres.schema_report.failed schema_version=%s error=%r",
                INITIAL_MIGRATION_NAME,
                exc,
            )
            return {
                "status": "degraded",
                "backend": self.backend_name,
                "schema_version": INITIAL_MIGRATION_NAME,
                "error": str(exc),
            }

    def _connect(self, *, row_factory=None):
        if self._pool is not None:
            conn_ctx = self._pool.connection()
            if row_factory is not None:
                class _PoolConnectionWithRowFactory:
                    def __init__(self, pool_ctx, rf):
                        self._pool_ctx = pool_ctx
                        self._rf = rf
                        self._conn = None
                    def __enter__(self):
                        self._conn = self._pool_ctx.__enter__()
                        self._conn.row_factory = self._rf
                        return self._conn
                    def __exit__(self, *args):
                        return self._pool_ctx.__exit__(*args)
                return _PoolConnectionWithRowFactory(conn_ctx, row_factory)
            return conn_ctx
        kwargs: dict[str, Any] = {"connect_timeout": self._connect_timeout_seconds}
        if row_factory is not None:
            kwargs["row_factory"] = row_factory
        return psycopg.connect(self._dsn, **kwargs)

    def _load_schema_columns(self) -> dict[str, set[str]]:
        query = """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
        ORDER BY table_name ASC, ordinal_position ASC
        """
        with self._connect(row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        columns: dict[str, set[str]] = {}
        for row in rows:
            table_name = row["table_name"]
            if table_name not in EXPECTED_SCHEMA_COLUMNS:
                continue
            columns.setdefault(table_name, set()).add(row["column_name"])
        return columns

    def _load_health_ping(self) -> dict[str, Any]:
        with self._connect(row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 AS ok")
                row = cursor.fetchone()
        return row or {"ok": 1}

    def _load_storage_counts(self) -> dict[str, int]:
        query = """
        SELECT
            (SELECT COUNT(*) FROM gk_tasks) AS task_count,
            (SELECT COUNT(*) FROM gk_task_steps) AS step_count,
            (SELECT COUNT(*) FROM gk_task_events) AS event_count
        """
        with self._connect(row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()
        if row is None:
            return {"task_count": 0, "step_count": 0, "event_count": 0}
        return {
            "task_count": int(row["task_count"]),
            "step_count": int(row["step_count"]),
            "event_count": int(row["event_count"]),
        }

    def _task_params(self, task: TaskRecord) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "status": task.status,
            "accepted_at": task.accepted_at,
            "completed_at": task.completed_at,
            "duration_ms": task.duration_ms,
            "prompt": task.prompt,
            "reasoning": task.reasoning,
            "execution_mode": task.execution_mode,
            "dry_run": task.dry_run,
            "model_count": task.model_count,
            "quorum": task.quorum,
            "merge_strategy": task.merge_strategy,
            "adapter_hint": task.adapter_hint,
            "cancel_on_quorum": task.cancel_on_quorum,
            "failure_code": task.failure_code,
            "failure_message": task.failure_message,
            "output_text": task.output_text,
            "metadata": json.dumps(task.metadata),
            "retry_of_task_id": task.retry_of_task_id,
        }

    def _save_task_with_steps_in_cursor(
        self,
        cursor,
        task: TaskRecord,
        steps: list[TaskStepRecord],
    ) -> None:
        cursor.execute(_TASK_UPSERT_QUERY, self._task_params(task))
        for step in steps:
            cursor.execute(_STEP_UPSERT_QUERY, self._step_params(step))

    def _step_params(self, step: TaskStepRecord) -> dict[str, Any]:
        return {
            "task_id": step.task_id,
            "step_index": step.step_index,
            "model_id": step.model_id,
            "model_display_name": step.model_display_name,
            "backend": step.backend,
            "provider": step.provider,
            "status": step.status,
            "failure_code": step.failure_code,
            "failure_message": step.failure_message,
            "output_text": step.output_text,
            "duration_ms": step.duration_ms,
        }

    def _append_event_in_cursor(self, cursor, event: TaskEventRecord) -> None:
        cursor.execute(
            _EVENT_INSERT_QUERY,
            {
                "event_id": event.event_id,
                "task_id": event.task_id,
                "sequence_no": event.sequence_no,
                "event_type": event.event_type,
                "created_at": event.created_at,
                "payload": json.dumps(event.payload),
            },
        )

    def _task_from_row(self, row: dict[str, Any]) -> TaskRecord:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return TaskRecord(
            task_id=row["task_id"],
            status=TaskStatus(row["status"]),
            accepted_at=row["accepted_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"],
            prompt=row["prompt"],
            reasoning=row["reasoning"],
            execution_mode=ExecutionMode(row["execution_mode"]),
            dry_run=row["dry_run"],
            model_count=row["model_count"],
            quorum=row["quorum"],
            merge_strategy=MergeStrategy(row["merge_strategy"]),
            adapter_hint=AdapterHint(row["adapter_hint"]),
            cancel_on_quorum=row["cancel_on_quorum"],
            failure_code=FailureCode(row["failure_code"]) if row["failure_code"] is not None else None,
            failure_message=row["failure_message"],
            output_text=row["output_text"],
            metadata=metadata,
            retry_of_task_id=row.get("retry_of_task_id"),
        )

    def _step_from_row(self, row: dict[str, Any]) -> TaskStepRecord:
        return TaskStepRecord(
            task_id=row["task_id"],
            step_index=row["step_index"],
            model_id=row["model_id"],
            model_display_name=row["model_display_name"],
            backend=row["backend"],
            provider=row["provider"],
            status=StepStatus(row["status"]),
            failure_code=FailureCode(row["failure_code"]) if row["failure_code"] is not None else None,
            failure_message=row["failure_message"],
            output_text=row["output_text"],
            duration_ms=row["duration_ms"],
        )

    def _event_from_row(self, row: dict[str, Any]) -> TaskEventRecord:
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        return TaskEventRecord(
            event_id=row["event_id"],
            task_id=row["task_id"],
            sequence_no=row["sequence_no"],
            event_type=EventType(row["event_type"]),
            created_at=row["created_at"],
            payload=payload,
        )
