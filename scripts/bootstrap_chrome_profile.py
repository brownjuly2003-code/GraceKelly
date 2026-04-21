from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a dedicated Chrome profile for GraceKelly.")
    parser.add_argument("--profile-dir", help="Profile directory. Defaults to ./chrome-profile relative to CWD.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without launching Chrome.")
    return parser.parse_args()


def find_browser() -> str:
    names = ("chrome.exe", "chrome", "google-chrome", "chromium", "chromium-browser")
    for name in names:
        candidate = shutil.which(name)
        if candidate:
            return candidate
    system = platform.system()
    paths = (
        (
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        )
        if system == "Windows"
        else (
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
        )
    )
    for path in paths:
        if path.exists():
            return str(path)
    raise RuntimeError("Chrome/Chromium not found.")


def terminate_tree(process: subprocess.Popen[bytes], profile_dir: Path) -> bool:
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if platform.system() == "Windows":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, **quiet)
    else:
        subprocess.run(["pkill", "-TERM", "-P", str(process.pid)], check=False, **quiet)
        subprocess.run(["kill", "-TERM", str(process.pid)], check=False, **quiet)
    locks = (profile_dir / "SingletonLock", profile_dir / "SingletonSocket", profile_dir / "SingletonCookie")
    for _ in range(100):
        try:
            process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            pass
        if process.poll() is not None and not any(lock.exists() for lock in locks):
            return True
    if platform.system() != "Windows":
        subprocess.run(["pkill", "-KILL", "-P", str(process.pid)], check=False, **quiet)
        subprocess.run(["kill", "-KILL", str(process.pid)], check=False, **quiet)
        for _ in range(100):
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
            if process.poll() is not None and not any(lock.exists() for lock in locks):
                return True
    return process.poll() is not None and not any(lock.exists() for lock in locks)


def main() -> int:
    args = parse_args()
    profile_dir = Path(args.profile_dir or Path.cwd() / "chrome-profile").resolve()
    browser = find_browser()
    command = [browser, f"--user-data-dir={profile_dir}", "https://www.perplexity.ai/"]
    print(f"Profile directory: {profile_dir}")
    print(f"Browser binary: {browser}")
    print(f"Launch command: {' '.join(command)}")
    print(f"export GRACEKELLY_BROWSER_PROFILE_DIR={profile_dir.as_posix()}")
    print("Reminder: do not open this profile with your regular Chrome session.")
    if args.dry_run:
        print("Dry run only. Chrome was not launched.")
        return 0
    profile_dir.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(command)
    try:
        input("Log into Perplexity in the opened Chrome window, then press Enter here.")
    except KeyboardInterrupt:
        print("\nInterrupted. Closing the launched browser tree.")
    if terminate_tree(process, profile_dir):
        print("Chrome shutdown confirmed and lock files are gone.")
        return 0
    print("Chrome shutdown could not be confirmed within 10 seconds. Close it manually before starting uvicorn.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
