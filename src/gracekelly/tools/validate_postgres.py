from __future__ import annotations

import argparse
from datetime import datetime
import json
import os

from gracekelly.storage.postgres import PostgresTaskRepository
from gracekelly.storage.schema import INITIAL_MIGRATION_NAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap and validate the GraceKelly PostgreSQL schema."
    )
    parser.add_argument(
        "--dsn",
        help="PostgreSQL DSN. Falls back to GRACEKELLY_POSTGRES_DSN.",
    )
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Skip schema bootstrap and run validation against the existing schema only.",
    )
    return parser.parse_args()


def resolve_dsn(cli_dsn: str | None) -> str | None:
    return cli_dsn or os.getenv("GRACEKELLY_POSTGRES_DSN")


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def main() -> int:
    args = parse_args()
    dsn = resolve_dsn(args.dsn)
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

    try:
        repository = PostgresTaskRepository(dsn, bootstrap=False)
        if not args.no_bootstrap:
            repository.bootstrap()
        health = repository.healthcheck()
        schema = repository.schema_report()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "migration": INITIAL_MIGRATION_NAME,
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 2

    report = {
        "status": "ok"
        if health["status"] == "ok" and schema["status"] == "ok"
        else "degraded",
        "migration": INITIAL_MIGRATION_NAME,
        "bootstrapped": not args.no_bootstrap,
        "health": health,
        "schema": schema,
    }
    print(json.dumps(report, indent=2, default=_json_default, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
