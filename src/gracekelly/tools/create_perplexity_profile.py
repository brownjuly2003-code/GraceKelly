from __future__ import annotations

import argparse
import os
from pathlib import Path

DEFAULT_PROFILE_DIR = str((Path(__file__).resolve().parents[3] / "tmp" / "browser-recon" / "perplexity-profile").resolve())
DEFAULT_BASE_URL = "https://www.perplexity.ai"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or refresh a dedicated Perplexity Playwright profile via manual login."
    )
    parser.add_argument(
        "--profile-dir",
        help="Persistent browser profile directory. Falls back to GRACEKELLY_BROWSER_PROFILE_DIR or the repo-local default.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("GRACEKELLY_BROWSER_BASE_URL", DEFAULT_BASE_URL),
        help=f"Browser start URL. Defaults to GRACEKELLY_BROWSER_BASE_URL or {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--channel",
        default=os.getenv("GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL", "chrome"),
        help="Browser channel passed to Playwright. Defaults to GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL or chrome.",
    )
    return parser.parse_args()


def resolve_profile_dir(cli_profile_dir: str | None) -> str:
    return cli_profile_dir or os.getenv("GRACEKELLY_BROWSER_PROFILE_DIR") or DEFAULT_PROFILE_DIR


def create_profile(
    *,
    profile_dir: str,
    base_url: str,
    channel: str,
    sync_playwright_factory=None,
    input_func=input,
    print_func=print,
) -> None:
    factory = sync_playwright_factory
    if factory is None:
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("playwright is required for browser profile creation.") from exc
        factory = sync_playwright

    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    print_func(f"Launching Playwright profile bootstrap at {profile_dir}")
    with factory() as playwright:
        context = playwright.chromium.launch_persistent_context(
            profile_dir,
            channel=channel,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(base_url, wait_until="domcontentloaded")
            print_func(f"Opened {base_url} in a persistent Playwright context.")
            input_func(
                "Log in to Perplexity in the opened browser window, wait for the prompt input to appear, then press Enter here."
            )
        finally:
            context.close()


def main() -> int:
    args = parse_args()
    profile_dir = resolve_profile_dir(args.profile_dir)
    try:
        create_profile(
            profile_dir=profile_dir,
            base_url=args.base_url,
            channel=args.channel,
        )
    except Exception as exc:
        print(f"Failed to create Perplexity profile: {exc}")
        return 2

    print(f"Perplexity profile is ready at {profile_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
