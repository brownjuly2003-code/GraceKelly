from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("gracekelly.recon_weekly")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_STATE_DIR = REPO_ROOT / ".workflow" / "state"
DEFAULT_DRIFT_LOG = REPO_ROOT / "logs" / "recon-drift.jsonl"
BASELINE_NAME = "perplexity-selectors-baseline.json"
LATEST_NAME = "perplexity-selectors-latest.json"
DRIFT_FLAG_NAME = "perplexity-selectors-drift.flag"

CaptureFunc = Callable[..., dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("recon.read_failed path=%s error=%r", path, exc)
        return None


def _snapshot_from_bundle(output_dir: pathlib.Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}

    home_buttons_path = output_dir / "recon-01-buttons.json"
    if home_buttons_path.exists():
        buttons = _read_json(home_buttons_path) or []
        snapshot["home_buttons"] = sorted(str(label) for label in buttons)

    model_menu_path = output_dir / "recon-03-model-menu.json"
    if model_menu_path.exists():
        menu = _read_json(model_menu_path) or []
        snapshot["model_menu"] = sorted(str(label) for label in menu)

    manifest_path = output_dir / "recon-99-manifest.json"
    if manifest_path.exists():
        manifest = _read_json(manifest_path) or {}
        snapshot["flags"] = {
            "direct_model_button_visible": manifest.get("direct_model_button_visible"),
            "more_button_visible": manifest.get("more_button_visible"),
            "more_clicked": manifest.get("more_clicked"),
            "model_button_visible_after_more": manifest.get("model_button_visible_after_more"),
        }
        files = manifest.get("files", {})
        snapshot["artefact_files"] = sorted(files.keys()) if isinstance(files, dict) else []

    return snapshot


def _diff_snapshots(baseline: dict[str, Any], latest: dict[str, Any]) -> dict[str, list[str]]:
    base_keys = set(baseline.keys())
    latest_keys = set(latest.keys())
    added = sorted(latest_keys - base_keys)
    removed = sorted(base_keys - latest_keys)
    changed = sorted(key for key in base_keys & latest_keys if baseline[key] != latest[key])
    return {"added": added, "removed": removed, "changed": changed}


def _write_json(path: pathlib.Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def _resolve_capture_func() -> CaptureFunc:
    from gracekelly.tools.capture_perplexity_recon import capture_recon

    return capture_recon


def run_recon(
    *,
    profile_dir: str,
    base_url: str = "https://www.perplexity.ai",
    channel: str = "chrome",
    state_dir: pathlib.Path = DEFAULT_STATE_DIR,
    drift_log_path: pathlib.Path = DEFAULT_DRIFT_LOG,
    capture_func: CaptureFunc | None = None,
) -> int:
    state_dir.mkdir(parents=True, exist_ok=True)
    drift_log_path.parent.mkdir(parents=True, exist_ok=True)

    baseline_path = state_dir / BASELINE_NAME
    latest_path = state_dir / LATEST_NAME
    flag_path = state_dir / DRIFT_FLAG_NAME

    capture = capture_func if capture_func is not None else _resolve_capture_func()

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = pathlib.Path(tmp_dir)
        capture(
            profile_dir=profile_dir,
            output_dir=str(output_dir),
            base_url=base_url,
            channel=channel,
        )
        snapshot = _snapshot_from_bundle(output_dir)

    _write_json(latest_path, snapshot)

    if not baseline_path.exists():
        _write_json(baseline_path, snapshot)
        if flag_path.exists():
            flag_path.unlink()
        logger.info("recon.baseline_created path=%s", baseline_path)
        return 0

    baseline = _read_json(baseline_path)
    if not isinstance(baseline, dict):
        logger.warning("recon.baseline_corrupt rebuilding path=%s", baseline_path)
        _write_json(baseline_path, snapshot)
        if flag_path.exists():
            flag_path.unlink()
        return 0

    diff = _diff_snapshots(baseline, snapshot)
    if not (diff["added"] or diff["removed"] or diff["changed"]):
        if flag_path.exists():
            flag_path.unlink()
        logger.info("recon.no_drift")
        return 0

    payload = {"ts": _now_iso(), **diff}
    with drift_log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _write_json(flag_path, payload)
    logger.warning(
        "recon.drift_detected added=%s removed=%s changed=%s",
        diff["added"],
        diff["removed"],
        diff["changed"],
    )
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Capture Perplexity DOM selectors and compare them against a stored baseline. "
            "Designed to run weekly via Windows Task Scheduler. Exits 0 when no drift, "
            "1 when drift is detected, 2 on argument errors."
        ),
    )
    parser.add_argument(
        "--profile-dir",
        default=os.getenv("GRACEKELLY_BROWSER_PROFILE_DIR"),
        help="Persistent Chrome profile directory. Falls back to GRACEKELLY_BROWSER_PROFILE_DIR.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("GRACEKELLY_BROWSER_BASE_URL", "https://www.perplexity.ai"),
        help="Perplexity start URL. Falls back to GRACEKELLY_BROWSER_BASE_URL.",
    )
    parser.add_argument(
        "--channel",
        default=os.getenv("GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL", "chrome"),
        help="Browser channel passed to Playwright. Falls back to GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    args = _build_parser().parse_args(argv)
    if not args.profile_dir:
        print(
            "ERROR: --profile-dir or GRACEKELLY_BROWSER_PROFILE_DIR is required.",
            file=sys.stderr,
        )
        return 2

    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

    return run_recon(
        profile_dir=args.profile_dir,
        base_url=args.base_url,
        channel=args.channel,
    )


if __name__ == "__main__":
    sys.exit(main())
