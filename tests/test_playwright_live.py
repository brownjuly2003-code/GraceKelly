from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
from gracekelly.adapters.browser.playwright_driver import PlaywrightBrowserAutomation, PlaywrightBrowserRuntimeConfig
from gracekelly.adapters.browser.policy import AuthRecoveryPolicy, ModelVerificationPolicy, PopupPolicy, SubmitPolicy
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    FailureCode,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import resolve_model


class PlaywrightBrowserLiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.getenv("GRACEKELLY_BROWSER_LIVE_TEST", "false").lower() != "true":
            raise unittest.SkipTest("Set GRACEKELLY_BROWSER_LIVE_TEST=true to run the live Playwright smoke.")
        profile_dir = os.getenv("GRACEKELLY_BROWSER_PROFILE_DIR")
        if not profile_dir:
            raise unittest.SkipTest("GRACEKELLY_BROWSER_PROFILE_DIR is required for the live Playwright smoke.")

        cls._adapter = PerplexityBrowserAdapter(
            session_manager=BrowserSessionManager(
                BrowserSessionConfig(
                    enabled=True,
                    provider="perplexity",
                    base_url=os.getenv("GRACEKELLY_BROWSER_BASE_URL", "https://www.perplexity.ai"),
                    profile_dir=profile_dir,
                )
            ),
            automation=PlaywrightBrowserAutomation(
                runtime=PlaywrightBrowserRuntimeConfig(
                    channel=os.getenv("GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL", "chrome"),
                    headless=os.getenv("GRACEKELLY_BROWSER_PLAYWRIGHT_HEADLESS", "false").lower() == "true",
                )
            ),
            popup_policy=PopupPolicy(),
            auth_recovery_policy=AuthRecoveryPolicy(allow_relogin=False),
            model_verification_policy=ModelVerificationPolicy(),
            submit_policy=SubmitPolicy(),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        adapter = getattr(cls, "_adapter", None)
        if adapter is None:
            return
        close_method = getattr(adapter._automation, "close", None)
        if callable(close_method):
            close_method()

    def build_request(self) -> ExecutionRequest:
        model = resolve_model(os.getenv("GRACEKELLY_BROWSER_LIVE_MODEL", "GPT-5.4"))
        step = ExecutionStep(
            model=model,
            backend=ExecutionBackend.BROWSER,
            provider=model.provider,
            provider_model_id=model.provider_model_id,
            step_index=1,
        )
        plan = ExecutionPlan(
            steps=(step,),
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            dry_run=False,
            adapter_hint=AdapterHint.AUTO,
            cancel_on_quorum=True,
        )
        return ExecutionRequest(
            task_id="playwright-live-smoke",
            prompt=os.getenv("GRACEKELLY_BROWSER_LIVE_PROMPT", "Reply with only OK"),
            plan=plan,
            step=step,
            reasoning=False,
            metadata={},
        )

    def test_live_playwright_backend_can_complete_authenticated_prompt(self) -> None:
        result = self._adapter.execute(self.build_request())

        if result.failure_code == FailureCode.AUTH_FAILED:
            self.skipTest(result.failure_message or "Profile is not authenticated for Perplexity.")

        if os.getenv("GRACEKELLY_BROWSER_LIVE_DEBUG", "false").lower() == "true":
            debug_path = Path(r"D:\GraceKelly\tmp\browser-recon\live-smoke-result.json")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(json.dumps(result.details, indent=2, sort_keys=True), encoding="utf-8")

        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertTrue(result.output_text.strip())
        self.assertIn("model_selection_verified", result.details)
        self.assertIn("response_source", result.details)


if __name__ == "__main__":
    unittest.main()
