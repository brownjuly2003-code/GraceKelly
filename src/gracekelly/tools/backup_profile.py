from __future__ import annotations

import argparse
import os
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_COOKIE_MARKERS: tuple[str, ...] = (
    "Cookies",
    "Cookies-journal",
    "Login Data",
    "Login Data-journal",
    "Local State",
    "Network/Cookies",
    "Network/Cookies-journal",
    "Preferences",
    "Secure Preferences",
    "Web Data",
    "Web Data-journal",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Snapshot critical files from a Chrome/Playwright profile into a tar.gz archive.",
    )
    parser.add_argument(
        "--profile-dir",
        help="Source profile directory. Falls back to GRACEKELLY_BROWSER_PROFILE_DIR.",
    )
    parser.add_argument(
        "--output-dir",
        default="backups",
        help="Destination directory for the archive. Defaults to ./backups.",
    )
    return parser.parse_args()


def resolve_profile_dir(cli_profile_dir: str | None) -> str:
    value = cli_profile_dir or os.getenv("GRACEKELLY_BROWSER_PROFILE_DIR")
    if not value:
        raise ValueError(
            "Profile directory not given. Pass --profile-dir or set GRACEKELLY_BROWSER_PROFILE_DIR."
        )
    return value


def collect_files(profile_dir: Path) -> list[Path]:
    found: list[Path] = []
    for marker in _COOKIE_MARKERS:
        candidate = profile_dir / marker
        if candidate.is_file():
            found.append(candidate)
    return found


def backup_profile(profile_dir: str, output_dir: str) -> Path:
    src = Path(profile_dir).resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"Profile directory does not exist: {src}")
    files = collect_files(src)
    if not files:
        raise RuntimeError(
            f"No recognised cookie/login files found in {src}. "
            "Either the profile was never used or the path points at the wrong directory."
        )

    dest_dir = Path(output_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    archive_path = dest_dir / f"perplexity-profile-{timestamp}.tar.gz"

    with tempfile.TemporaryDirectory() as staging:
        staging_dir = Path(staging)
        for source in files:
            relative = source.relative_to(src)
            target = staging_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(staging_dir, arcname=f"profile-{timestamp}")

    return archive_path


def main() -> int:
    args = parse_args()
    try:
        profile_dir = resolve_profile_dir(args.profile_dir)
        archive = backup_profile(profile_dir, args.output_dir)
    except Exception as exc:
        print(f"Backup failed: {exc}")
        return 2
    print(f"Profile backup saved: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
