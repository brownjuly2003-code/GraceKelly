from __future__ import annotations

import argparse
import json
import os
from datetime import datetime

from gracekelly.storage.postgres import PostgresTaskRepository
from gracekelly.storage.schema import discover_migrations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply pending GraceKelly PostgreSQL migrations."
    )
    parser.add_argument(
        "--dsn",
        help="PostgreSQL DSN. Falls back to GRACEKELLY_POSTGRES_DSN.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pending migrations without applying them.",
    )
    return parser.parse_args()


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main() -> int:
    args = parse_args()
    dsn = args.dsn or os.getenv("GRACEKELLY_POSTGRES_DSN")
    if not dsn:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "A PostgreSQL DSN is required via --dsn or GRACEKELLY_POSTGRES_DSN.",
                },
                indent=2,
            )
        )
        return 2

    available = discover_migrations()

    if args.dry_run:
        try:
            repository = PostgresTaskRepository(dsn, bootstrap=False)
            applied = repository.applied_migrations()
        except Exception:
            applied = []
        pending = [m for m in available if m not in set(applied)]
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "migrations_available": available,
                    "migrations_applied": applied,
                    "migrations_pending": pending,
                },
                indent=2,
                default=_json_default,
            )
        )
        return 0

    try:
        repository = PostgresTaskRepository(dsn, bootstrap=True)
        schema = repository.schema_report()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": "ok" if schema["status"] == "ok" else "degraded",
                "migrations_available": schema.get("migrations_available", available),
                "migrations_applied": schema.get("migrations_applied", []),
                "migrations_pending": schema.get("migrations_pending", []),
                "schema": schema,
            },
            indent=2,
            default=_json_default,
            sort_keys=True,
        )
    )
    return 0 if schema["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
