from __future__ import annotations

import json
import os
from pathlib import Path
import time
import unittest

from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
from gracekelly.adapters.browser.playwright_driver import PlaywrightBrowserAutomation, PlaywrightBrowserRuntimeConfig
from gracekelly.adapters.browser.policy import AuthRecoveryPolicy, ModelVerificationPolicy, PopupPolicy, SubmitPolicy
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
from gracekelly.core.consensus import ConsensusConfig
from gracekelly.core.consensus_execution import ConsensusExecutionConfig, ConsensusExecutor
from gracekelly.core.contracts import ExecutionBackend, ExecutionPlan, ExecutionRequest, ExecutionStep, MergeStrategy, StepStatus
from gracekelly.core.embeddings import EmbeddingsClient
from gracekelly.core.models import resolve_model
from gracekelly.core.similarity import cosine_similarity
from gracekelly.core.clustering_hac import hac_cluster
from gracekelly.core.cluster_confidence import compute_cluster_confidence


LIVE_MODELS = ["GPT-5.4", "Gemini 3.1 Pro", "Claude Sonnet 4.6"]
LIVE_PROMPT = "What are the three most important principles of software engineering? Be concise — one sentence per principle."


class LiveMultiModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.getenv("GRACEKELLY_BROWSER_LIVE_TEST", "false").lower() != "true":
            raise unittest.SkipTest("Set GRACEKELLY_BROWSER_LIVE_TEST=true")
        profile_dir = os.getenv("GRACEKELLY_BROWSER_PROFILE_DIR")
        if not profile_dir:
            raise unittest.SkipTest("GRACEKELLY_BROWSER_PROFILE_DIR required")
        mistral_key = os.getenv("GRACEKELLY_MISTRAL_API_KEY")
        if not mistral_key:
            raise unittest.SkipTest("GRACEKELLY_MISTRAL_API_KEY required for embeddings")

        cls._adapter = PerplexityBrowserAdapter(
            session_manager=BrowserSessionManager(
                BrowserSessionConfig(
                    enabled=True,
                    provider="perplexity",
                    base_url="https://www.perplexity.ai",
                    profile_dir=profile_dir,
                )
            ),
            automation=PlaywrightBrowserAutomation(
                runtime=PlaywrightBrowserRuntimeConfig(
                    channel="chrome",
                    headless=False,
                )
            ),
            popup_policy=PopupPolicy(),
            auth_recovery_policy=AuthRecoveryPolicy(allow_relogin=False),
            model_verification_policy=ModelVerificationPolicy(),
            submit_policy=SubmitPolicy(),
        )
        cls._embeddings = EmbeddingsClient(
            api_key=mistral_key,
            base_url="https://api.mistral.ai/v1",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        adapter = getattr(cls, "_adapter", None)
        if adapter is None:
            return
        close_method = getattr(adapter._automation, "close", None)
        if callable(close_method):
            close_method()

    def _execute_model(self, model_name: str) -> dict:
        model = resolve_model(model_name)
        step = ExecutionStep(
            model=model,
            backend=ExecutionBackend.BROWSER,
            provider=model.provider,
            provider_model_id=model.provider_model_id,
            step_index=0,
        )
        plan = ExecutionPlan(
            steps=(step,),
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            dry_run=False,
            adapter_hint="auto",
            cancel_on_quorum=False,
        )
        request = ExecutionRequest(
            task_id=f"live-multi-{model.id}",
            prompt=LIVE_PROMPT,
            plan=plan,
            step=step,
            reasoning=True,
        )

        t0 = time.monotonic()
        result = self._adapter.execute(request)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        return {
            "model_id": model.id,
            "model_name": model_name,
            "status": result.status.value,
            "output_text": result.output_text[:500] if result.output_text else "",
            "thinking_enabled": result.details.get("thinking_enabled", False),
            "duration_ms": elapsed_ms,
        }

    def test_multi_model_consensus(self) -> None:
        models_to_test = os.getenv("GRACEKELLY_LIVE_MODELS", ",".join(LIVE_MODELS)).split(",")
        models_to_test = [m.strip() for m in models_to_test if m.strip()]

        results = []
        for model_name in models_to_test:
            result = self._execute_model(model_name)
            results.append(result)
            if result["status"] != "completed":
                continue
            time.sleep(2)

        completed = [r for r in results if r["status"] == "completed"]
        self.assertGreaterEqual(len(completed), 2, f"Need at least 2 completed responses, got {len(completed)}")

        responses = [r["output_text"] for r in completed]
        embeddings = self._embeddings.embed_batch(responses)

        n = len(embeddings)
        sim_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                sim_matrix[i][j] = cosine_similarity(embeddings[i], embeddings[j])

        hac_result = hac_cluster(sim_matrix)
        conf_result = compute_cluster_confidence(hac_result.clusters, sim_matrix)

        consensus_report = {
            "prompt": LIVE_PROMPT,
            "models_attempted": len(results),
            "models_completed": len(completed),
            "model_results": results,
            "consensus_score": conf_result.confidence,
            "num_clusters": hac_result.num_clusters,
            "is_unanimous": conf_result.is_unanimous,
            "top_cluster_size": conf_result.top_cluster_size,
            "similarity_matrix": [[round(s, 3) for s in row] for row in sim_matrix],
        }

        debug_path = Path(r"D:\GraceKelly\tmp\browser-recon\multi-model-consensus.json")
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(json.dumps(consensus_report, indent=2, ensure_ascii=False), encoding="utf-8")

        self.assertGreater(conf_result.confidence, 0.0)
        self.assertGreaterEqual(hac_result.num_clusters, 1)


if __name__ == "__main__":
    unittest.main()
