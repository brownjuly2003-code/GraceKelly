from __future__ import annotations

"""Shared auth-facing error codes. Mapping: .workflow/docs/auth-error-codes.md."""

AUTH_SYNC_HTTP_CODE = "model_auth_required"
AUTH_TASK_FAILURE_CODE = "auth_failed"

__all__ = ["AUTH_SYNC_HTTP_CODE", "AUTH_TASK_FAILURE_CODE"]
