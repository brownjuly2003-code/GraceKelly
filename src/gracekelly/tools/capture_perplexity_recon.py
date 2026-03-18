from __future__ import annotations

import argparse
from datetime import date, datetime, UTC
import json
import os
from pathlib import Path
import time
from typing import Any

from gracekelly.adapters.browser.selectors import PerplexitySelectors
from gracekelly.tools.create_perplexity_profile import DEFAULT_BASE_URL, resolve_profile_dir

DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parents[3] / "tmp" / "browser-recon"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture a fresh authenticated Perplexity DOM reconnaissance bundle from a dedicated Playwright profile."
    )
    parser.add_argument(
        "--profile-dir",
        help="Persistent browser profile directory. Falls back to GRACEKELLY_BROWSER_PROFILE_DIR or the repo-local default.",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for screenshots and JSON/HTML artifacts. Defaults to GRACEKELLY_BROWSER_RECON_DIR or tmp/browser-recon/YYYY-MM-DD.",
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
    parser.add_argument(
        "--interactive-pause",
        action="store_true",
        help="Pause after the automatic capture so you can click through the live UI manually before the final screenshot.",
    )
    return parser.parse_args()


def resolve_output_dir(cli_output_dir: str | None, *, today: date | None = None) -> str:
    if cli_output_dir:
        return cli_output_dir
    env_output_dir = os.getenv("GRACEKELLY_BROWSER_RECON_DIR")
    if env_output_dir:
        return env_output_dir
    stamp = (today or date.today()).isoformat()
    return str((DEFAULT_OUTPUT_ROOT / stamp).resolve())


def capture_recon(
    *,
    profile_dir: str,
    output_dir: str,
    base_url: str,
    channel: str,
    interactive_pause: bool = False,
    selectors: PerplexitySelectors | None = None,
    sync_playwright_factory=None,
    input_func=input,
    print_func=print,
) -> dict[str, object]:
    factory = sync_playwright_factory
    if factory is None:
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError("playwright is required for Perplexity DOM reconnaissance.") from exc
        factory = sync_playwright

    selector_config = selectors or PerplexitySelectors()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    print_func(f"Launching Perplexity DOM recon with profile {profile_dir}")
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
            _wait_for_shell(page, selectors=selector_config)

            manifest: dict[str, object] = {
                "profile_dir": profile_dir,
                "output_dir": str(output_root),
                "base_url": base_url,
                "captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "interactive_pause": interactive_pause,
                "files": {},
            }

            home_shot = output_root / "recon-01-home.png"
            page.screenshot(path=str(home_shot), full_page=True)
            home_buttons = _button_inventory(page)
            home_buttons_path = output_root / "recon-01-buttons.json"
            _write_json(home_buttons_path, home_buttons)
            composer_html_path = output_root / "recon-01-composer.html"
            composer_html = _composer_html(page, selectors=selector_config)
            composer_html_path.write_text(composer_html, encoding="utf-8")

            manifest["files"] = {
                "home_screenshot": home_shot.name,
                "home_buttons": home_buttons_path.name,
                "composer_html": composer_html_path.name,
            }

            direct_model_visible = _click_if_visible(page, selector_config.model_button)
            more_visible = _is_visible(page, selector_config.more_button)
            manifest["direct_model_button_visible"] = direct_model_visible
            manifest["more_button_visible"] = more_visible

            more_clicked = False
            if direct_model_visible:
                model_picker_path = output_root / "recon-03-model-picker.png"
                page.screenshot(path=str(model_picker_path), full_page=True)
                model_menu_path = output_root / "recon-03-model-menu.json"
                _write_json(model_menu_path, _model_menu_snapshot(page, selectors=selector_config))
                manifest["files"]["model_picker_screenshot"] = model_picker_path.name
                manifest["files"]["model_menu_snapshot"] = model_menu_path.name
            elif _click_more(page, selector_config):
                more_clicked = True
                more_shot = output_root / "recon-02-more.png"
                page.screenshot(path=str(more_shot), full_page=True)
                more_buttons_path = output_root / "recon-02-buttons.json"
                _write_json(more_buttons_path, _button_inventory(page))
                manifest["files"]["more_screenshot"] = more_shot.name
                manifest["files"]["more_buttons"] = more_buttons_path.name

                model_button_after_more = _click_if_visible(page, selector_config.model_button)
                manifest["model_button_visible_after_more"] = model_button_after_more
                if model_button_after_more:
                    model_picker_path = output_root / "recon-03-model-picker.png"
                    page.screenshot(path=str(model_picker_path), full_page=True)
                    model_menu_path = output_root / "recon-03-model-menu.json"
                    _write_json(model_menu_path, _model_menu_snapshot(page, selectors=selector_config))
                    manifest["files"]["model_picker_screenshot"] = model_picker_path.name
                    manifest["files"]["model_menu_snapshot"] = model_menu_path.name
            manifest["more_clicked"] = more_clicked

            if interactive_pause:
                input_func(
                    "If needed, click through the live Perplexity UI now, then press Enter to capture the final manual-state artifacts."
                )
                manual_shot = output_root / "recon-98-manual.png"
                page.screenshot(path=str(manual_shot), full_page=True)
                manual_buttons_path = output_root / "recon-98-buttons.json"
                _write_json(manual_buttons_path, _button_inventory(page))
                manifest["files"]["manual_screenshot"] = manual_shot.name
                manifest["files"]["manual_buttons"] = manual_buttons_path.name

            manifest_path = output_root / "recon-99-manifest.json"
            _write_json(manifest_path, manifest)
            print_func(f"Perplexity DOM recon bundle captured at {output_root}")
            return manifest
        finally:
            context.close()


def main() -> int:
    args = parse_args()
    profile_dir = resolve_profile_dir(args.profile_dir)
    output_dir = resolve_output_dir(args.output_dir)
    try:
        capture_recon(
            profile_dir=profile_dir,
            output_dir=output_dir,
            base_url=args.base_url,
            channel=args.channel,
            interactive_pause=args.interactive_pause,
        )
    except Exception as exc:
        print(f"Failed to capture Perplexity DOM recon: {exc}")
        return 2

    print(f"Perplexity DOM recon is ready at {output_dir}")
    return 0


def _wait_for_shell(page: Any, *, selectors: PerplexitySelectors, timeout_seconds: int = 10) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _is_visible(page, selectors.prompt_input):
            return
        body_text = _body_text(page)
        if any(marker in body_text for marker in selectors.signed_out_markers):
            return
        if all(marker in body_text for marker in selectors.ready_markers[:2]):
            return
        time.sleep(0.5)
    raise TimeoutError("Perplexity shell did not become ready for recon capture.")


def _button_inventory(page: Any) -> list[str]:
    try:
        entries = page.evaluate(
            """
            () => Array.from(document.querySelectorAll('button')).slice(0, 24).map((button) => {
              const ariaLabel = button.getAttribute('aria-label');
              const text = (button.innerText || '').trim();
              return ariaLabel ? `${ariaLabel}::${text}` : text;
            })
            """
        )
    except Exception:
        return []
    if not isinstance(entries, list):
        return []
    return [str(entry).strip() for entry in entries if str(entry).strip()]


def _composer_html(page: Any, *, selectors: PerplexitySelectors) -> str:
    for candidate in ("form", "main", selectors.prompt_input):
        locator = page.locator(candidate)
        if _locator_exists(locator):
            try:
                return locator.first.inner_html()
            except Exception:
                continue
    return ""


def _click_more(page: Any, selectors: PerplexitySelectors) -> bool:
    candidates = (
        selectors.more_button,
        'button:has-text("More")',
    )
    for candidate in candidates:
        if _click_if_visible(page, candidate):
            return True
    return False


def _model_menu_snapshot(page: Any, *, selectors: PerplexitySelectors) -> list[str]:
    texts: list[str] = []
    for selector in selectors.model_menu_candidates:
        try:
            texts.extend(page.locator(selector).all_inner_texts())
        except Exception:
            continue
    lines: list[str] = []
    for block in texts:
        for line in str(block).splitlines():
            normalized = line.strip()
            if normalized and normalized not in lines:
                lines.append(normalized)
    return lines


def _click_if_visible(page: Any, selector: str) -> bool:
    locator = page.locator(selector)
    if not _locator_is_visible(locator):
        return False
    locator.first.click()
    time.sleep(0.2)
    return True


def _is_visible(page: Any, selector: str) -> bool:
    return _locator_is_visible(page.locator(selector))


def _locator_is_visible(locator: Any) -> bool:
    candidate = getattr(locator, "first", locator)
    is_visible = getattr(candidate, "is_visible", None)
    if callable(is_visible):
        try:
            return bool(is_visible())
        except Exception:
            return False
    count = getattr(candidate, "count", None)
    if callable(count):
        try:
            return bool(count())
        except Exception:
            return False
    return False


def _locator_exists(locator: Any) -> bool:
    candidate = getattr(locator, "first", locator)
    count = getattr(candidate, "count", None)
    if callable(count):
        try:
            return bool(count())
        except Exception:
            return False
    return _locator_is_visible(candidate)


def _body_text(page: Any) -> str:
    try:
        return page.inner_text("body")
    except Exception:
        return ""


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
