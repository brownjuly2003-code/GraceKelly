from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi.testclient not installed")
class TaskSearchAndExportTests(unittest.TestCase):
    def setUp(self) -> None:
        from gracekelly.main import create_app

        self.client = TestClient(create_app())
        self.addCleanup(self.client.close)

    def _create_task(self, prompt: str) -> str:
        response = self.client.post(
            "/api/v1/orchestrate",
            json={"prompt": prompt, "model": "Kimi K2", "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["task_id"]

    def test_prompt_contains_filter_returns_matching_tasks(self) -> None:
        alpha_task_id = self._create_task("alpha query here")
        self._create_task("beta query here")

        response = self.client.get("/api/v1/tasks", params={"prompt_contains": "ALPHA"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["task_id"] for item in response.json()], [alpha_task_id])

    def test_prompt_contains_no_match_returns_empty(self) -> None:
        self._create_task("alpha query here")

        response = self.client.get("/api/v1/tasks", params={"prompt_contains": "zzznomatch_xq9"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_export_returns_markdown(self) -> None:
        task_id = self._create_task("export test prompt")

        response = self.client.get(f"/api/v1/tasks/{task_id}/export")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/markdown", response.headers["content-type"])
        self.assertIn("export test prompt", response.text)
        self.assertIn("## Prompt", response.text)
        self.assertIn("## Output", response.text)

    def test_export_404_for_unknown_task(self) -> None:
        response = self.client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000/export")

        self.assertEqual(response.status_code, 404)
