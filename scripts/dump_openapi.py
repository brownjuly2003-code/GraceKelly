"""Dump the FastAPI OpenAPI schema to docs-site/openapi.json.

Run locally (the docs build runs on a Node-only CI runner, so the schema is
committed as a build input rather than generated in CI):

    python scripts/dump_openapi.py

The browser adapter is disabled so the dump never needs a Chromium binary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("GRACEKELLY_BROWSER_ENABLED", "false")

from gracekelly.main import create_app


def main() -> None:
    app = create_app()
    spec = app.openapi()
    out = Path(__file__).resolve().parents[1] / "docs-site" / "openapi.json"
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(spec.get('paths', {}))} paths, "
          f"{len(spec.get('components', {}).get('schemas', {}))} schemas)")


if __name__ == "__main__":
    main()
