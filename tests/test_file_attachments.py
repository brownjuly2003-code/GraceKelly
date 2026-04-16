from __future__ import annotations

import asyncio
import io
import sys
import types
import unittest
from unittest.mock import patch

try:
    from fastapi import UploadFile
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    HAS_TEST_CLIENT = False
else:
    HAS_TEST_CLIENT = True

from starlette.datastructures import Headers

from gracekelly.api.routes.orchestrate import _extract_file_content
from gracekelly.core.contracts import (
    ATTACHMENT_METADATA_KEY,
    AdapterHint,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    FileAttachment,
    MergeStrategy,
    discard_registered_attachments,
    register_file_attachments,
)
from gracekelly.core.models import ModelSpec

if HAS_TEST_CLIENT:
    from gracekelly.config import Settings
    from gracekelly.main import create_app


_MODEL = ModelSpec(
    id="mistral-small",
    display_name="Mistral Small",
    aliases=("Mistral",),
    adapter_kind="api",
    provider="mistral",
    provider_model_id="mistral-small-latest",
    timeout_seconds=30,
    expected_latency_class="fast",
    concurrency_limit=4,
    reasoning_capable=False,
)

_STEP = ExecutionStep(
    model=_MODEL,
    backend=ExecutionBackend.API,
    provider="mistral",
    provider_model_id="mistral-small-latest",
    step_index=1,
)

_PLAN = ExecutionPlan(
    steps=(_STEP,),
    quorum=1,
    merge_strategy=MergeStrategy.FIRST_SUCCESS,
    dry_run=True,
    adapter_hint=AdapterHint.AUTO,
    cancel_on_quorum=True,
)


def _make_upload(filename: str, data: bytes, content_type: str | None = None) -> UploadFile:
    headers = None
    if content_type is not None:
        headers = Headers({"content-type": content_type})
    return UploadFile(filename=filename, file=io.BytesIO(data), headers=headers)


class FileExtractionTests(unittest.TestCase):
    def test_txt_file_extracted_as_text(self) -> None:
        text, attachment = asyncio.run(_extract_file_content(_make_upload("notes.txt", b"hello", "text/plain")))

        self.assertEqual(text, "[File: notes.txt]\nhello")
        self.assertIsNone(attachment)

    def test_pdf_text_extracted_when_pypdf_available(self) -> None:
        fake_module = types.SimpleNamespace(
            PdfReader=lambda _: types.SimpleNamespace(
                pages=[
                    types.SimpleNamespace(extract_text=lambda: "page 1"),
                    types.SimpleNamespace(extract_text=lambda: "page 2"),
                ]
            )
        )

        with patch.dict(sys.modules, {"pypdf": fake_module}):
            text, attachment = asyncio.run(
                _extract_file_content(_make_upload("scan.pdf", b"%PDF-1.4", "application/pdf"))
            )

        self.assertEqual(text, "[File: scan.pdf]\npage 1\npage 2")
        self.assertIsNone(attachment)

    def test_image_becomes_file_attachment(self) -> None:
        text, attachment = asyncio.run(
            _extract_file_content(_make_upload("photo.png", b"png-bytes", "image/png"))
        )

        self.assertIsNone(text)
        self.assertEqual(
            attachment,
            FileAttachment(name="photo.png", content_type="image/png", data=b"png-bytes"),
        )

    def test_unsupported_format_raises_422(self) -> None:
        with self.assertRaisesRegex(Exception, "Unsupported file type"):
            asyncio.run(_extract_file_content(_make_upload("archive.zip", b"zip", "application/zip")))


class AttachmentRegistryTests(unittest.TestCase):
    def test_execution_request_resolves_registered_attachments_from_metadata(self) -> None:
        attachment = FileAttachment(name="photo.png", content_type="image/png", data=b"img")
        token = register_file_attachments((attachment,))
        try:
            request = ExecutionRequest(
                task_id="t1",
                prompt="look",
                plan=_PLAN,
                step=_STEP,
                reasoning=False,
                metadata={ATTACHMENT_METADATA_KEY: token},
            )
        finally:
            discard_registered_attachments(token)

        self.assertEqual(request.attachments, (attachment,))


@unittest.skipIf(not HAS_TEST_CLIENT, "fastapi.testclient is not installed")
class OrchestrateUploadEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            Settings(
                env="test",
                host="127.0.0.1",
                port=8011,
                log_level="INFO",
                storage_backend="memory",
                postgres_dsn=None,
                mistral_api_key=None,
                mistral_base_url="https://api.mistral.ai/v1",
                mistral_timeout_seconds=1.0,
                openai_api_key=None,
                openai_base_url="https://api.openai.com/v1",
                openai_timeout_seconds=1.0,
                browser_enabled=False,
                browser_profile_dir=None,
                browser_base_url="https://www.perplexity.ai",
            )
        )
        self.client = TestClient(self.app)

    def test_upload_with_txt_file_appends_to_prompt(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate/upload",
            data={"prompt": "Base prompt", "model": "mistral-small", "dry_run": "true"},
            files=[("files", ("notes.txt", b"hello world", "text/plain"))],
        )

        self.assertEqual(response.status_code, 200)
        task = self.client.get(f"/api/v1/tasks/{response.json()['task_id']}").json()
        self.assertIn("Base prompt", task["prompt"])
        self.assertIn("[File: notes.txt]\nhello world", task["prompt"])

    def test_upload_with_image_creates_attachment(self) -> None:
        captured: dict[str, tuple[FileAttachment, ...]] = {}
        original_execute = self.app.state.dry_run_adapter.execute

        def wrapped_execute(request: ExecutionRequest):  # type: ignore[no-untyped-def]
            captured["attachments"] = request.attachments
            return original_execute(request)

        self.app.state.dry_run_adapter.execute = wrapped_execute
        response = self.client.post(
            "/api/v1/orchestrate/upload",
            data={"prompt": "Describe image", "model": "mistral-small", "dry_run": "true"},
            files=[("files", ("photo.png", b"png-bytes", "image/png"))],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(captured["attachments"]), 1)
        self.assertEqual(captured["attachments"][0].name, "photo.png")
        task = self.client.get(f"/api/v1/tasks/{response.json()['task_id']}").json()
        self.assertEqual(task["metadata"], {})

    def test_upload_no_files_works_like_regular_orchestrate(self) -> None:
        response = self.client.post(
            "/api/v1/orchestrate/upload",
            data={"prompt": "Base prompt", "model": "mistral-small", "dry_run": "true"},
        )

        self.assertEqual(response.status_code, 200)
        task = self.client.get(f"/api/v1/tasks/{response.json()['task_id']}").json()
        self.assertEqual(task["prompt"], "Base prompt")

    def test_upload_with_pdf_extracts_text(self) -> None:
        fake_module = types.SimpleNamespace(
            PdfReader=lambda _: types.SimpleNamespace(pages=[types.SimpleNamespace(extract_text=lambda: "pdf text")])
        )

        with patch.dict(sys.modules, {"pypdf": fake_module}):
            response = self.client.post(
                "/api/v1/orchestrate/upload",
                data={"prompt": "Summarize", "model": "mistral-small", "dry_run": "true"},
                files=[("files", ("scan.pdf", b"%PDF-1.4", "application/pdf"))],
            )

        self.assertEqual(response.status_code, 200)
        task = self.client.get(f"/api/v1/tasks/{response.json()['task_id']}").json()
        self.assertIn("[File: scan.pdf]\npdf text", task["prompt"])


if __name__ == "__main__":
    unittest.main()
