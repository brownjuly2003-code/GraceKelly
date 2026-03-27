from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from gracekelly.adapters.browser.playwright_driver import PlaywrightBrowserAutomation, PlaywrightBrowserRuntimeConfig
from gracekelly.adapters.browser.selectors import PerplexitySelectors
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager


class ThinkingReconTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.getenv("GRACEKELLY_BROWSER_LIVE_TEST", "false").lower() != "true":
            raise unittest.SkipTest("Set GRACEKELLY_BROWSER_LIVE_TEST=true")
        profile_dir = os.getenv("GRACEKELLY_BROWSER_PROFILE_DIR")
        if not profile_dir:
            raise unittest.SkipTest("GRACEKELLY_BROWSER_PROFILE_DIR required")

        import time
        cls._selectors = PerplexitySelectors()
        cls._automation = PlaywrightBrowserAutomation(
            runtime=PlaywrightBrowserRuntimeConfig(
                channel=os.getenv("GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL", "chrome"),
                headless=False,
            )
        )
        session_manager = BrowserSessionManager(
            BrowserSessionConfig(
                enabled=True,
                provider="perplexity",
                base_url="https://www.perplexity.ai",
                profile_dir=profile_dir,
            )
        )
        cls._automation.ensure_session(session_manager)
        time.sleep(3)

    @classmethod
    def tearDownClass(cls) -> None:
        automation = getattr(cls, "_automation", None)
        if automation:
            automation.close()

    def test_recon_thinking_toggle(self) -> None:
        import time
        page = self._automation._page_or_raise()

        model_button = self._automation._resolve_model_button(page, attempts=5)
        self.assertIsNotNone(model_button, "Model button not found")

        button_text_before = self._automation._locator_inner_text(model_button)

        model_button.click()
        time.sleep(1)

        menu_texts = self._automation._model_menu_texts(page)

        menu_html = ""
        for selector in self._selectors.model_menu_candidates:
            try:
                locator = page.locator(selector)
                if self._automation._locator_is_visible(locator):
                    menu_html = locator.first.inner_html()
                    break
            except Exception:
                continue

        thinking_items = []
        try:
            thinking_by_text = page.get_by_text("Thinking", exact=True)
            thinking_count = thinking_by_text.count()
            for i in range(thinking_count):
                item = thinking_by_text.nth(i)
                tag = item.evaluate("el => el.tagName")
                role = item.evaluate("el => el.getAttribute('role')")
                aria = item.evaluate("el => el.getAttribute('aria-checked') || el.getAttribute('aria-pressed') || el.getAttribute('data-state') || ''")
                parent_tag = item.evaluate("el => el.parentElement ? el.parentElement.tagName : ''")
                parent_role = item.evaluate("el => el.parentElement ? el.parentElement.getAttribute('role') || '' : ''")
                thinking_items.append({
                    "tag": tag,
                    "role": role,
                    "aria_state": aria,
                    "parent_tag": parent_tag,
                    "parent_role": parent_role,
                    "visible": item.is_visible(),
                })
        except Exception as e:
            thinking_items.append({"error": str(e)})

        thinking_click_result = {}
        try:
            thinking_el = page.get_by_text("Thinking", exact=True).first
            if thinking_el.is_visible():
                parent_state_before = thinking_el.evaluate("el => el.closest('[data-state]')?.getAttribute('data-state') || ''")
                thinking_el.click()
                time.sleep(1)

                parent_state_after = thinking_el.evaluate("el => el.closest('[data-state]')?.getAttribute('data-state') || ''")
                menu_texts_after = self._automation._model_menu_texts(page)
                menu_html_after = ""
                for selector in self._selectors.model_menu_candidates:
                    try:
                        locator = page.locator(selector)
                        if self._automation._locator_is_visible(locator):
                            menu_html_after = locator.first.inner_html()
                            break
                    except Exception:
                        continue

                thinking_click_result = {
                    "parent_state_before": parent_state_before,
                    "parent_state_after": parent_state_after,
                    "menu_texts_after": menu_texts_after,
                    "menu_html_after_snippet": menu_html_after[:3000],
                }

                model_button_after = self._automation._resolve_model_button(page, attempts=3)
                if model_button_after:
                    thinking_click_result["button_text_after_click"] = self._automation._locator_inner_text(model_button_after)
        except Exception as e:
            thinking_click_result = {"click_error": str(e)}

        page.keyboard.press("Escape")
        time.sleep(0.5)

        model_button_final = self._automation._resolve_model_button(page, attempts=3)
        button_text_final = self._automation._locator_inner_text(model_button_final) if model_button_final else "N/A"

        result = {
            "button_text_before": button_text_before,
            "button_text_final": button_text_final,
            "menu_texts": menu_texts,
            "menu_html_length": len(menu_html),
            "menu_html_snippet": menu_html[:3000],
            "thinking_items": thinking_items,
            "thinking_click_result": thinking_click_result,
        }

        debug_path = Path(r"D:\GraceKelly\tmp\browser-recon\thinking-recon.json")
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        self.assertTrue(len(menu_texts) > 0, "Model menu was empty")


if __name__ == "__main__":
    unittest.main()
