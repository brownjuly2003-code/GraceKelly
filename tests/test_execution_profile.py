from __future__ import annotations

import unittest

from gracekelly.core.execution_profile import (
    PROFILES,
    ExecutionProfile,
    resolve_execution_profile,
)


class ExecutionProfileTests(unittest.TestCase):
    def test_resolve_dry_run(self) -> None:
        profile = resolve_execution_profile("dry-run")
        self.assertEqual(profile.name, "dry-run")
        self.assertIn("dry-run", profile.required_adapters)

    def test_resolve_api_only(self) -> None:
        profile = resolve_execution_profile("api-only")
        self.assertEqual(profile.name, "api-only")
        self.assertIn("dry-run", profile.required_adapters)
        self.assertIn("api.mistral", profile.required_adapters)

    def test_resolve_hybrid(self) -> None:
        profile = resolve_execution_profile("hybrid")
        self.assertIn("browser.perplexity", profile.required_adapters)

    def test_resolve_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve_execution_profile("nonexistent")

    def test_is_required(self) -> None:
        profile = resolve_execution_profile("api-only")
        self.assertTrue(profile.is_required("api.mistral"))
        self.assertFalse(profile.is_required("browser.perplexity"))

    def test_is_known_required(self) -> None:
        profile = resolve_execution_profile("dry-run")
        self.assertTrue(profile.is_known("dry-run"))

    def test_is_known_optional(self) -> None:
        profile = resolve_execution_profile("dry-run")
        self.assertTrue(profile.is_known("browser.perplexity"))

    def test_is_known_unknown(self) -> None:
        profile = resolve_execution_profile("dry-run")
        self.assertFalse(profile.is_known("nonexistent.adapter"))

    def test_storage_required_default(self) -> None:
        for name, profile in PROFILES.items():
            self.assertTrue(profile.storage_required, f"{name} should require storage")

    def test_all_profiles_have_dry_run(self) -> None:
        for name, profile in PROFILES.items():
            self.assertIn(
                "dry-run",
                profile.required_adapters | profile.optional_adapters,
                f"{name} should include dry-run",
            )

    def test_profile_is_frozen(self) -> None:
        profile = resolve_execution_profile("dry-run")
        with self.assertRaises(AttributeError):
            profile.name = "hacked"  # type: ignore[misc]

    def test_hybrid_optional_includes_openai(self) -> None:
        profile = resolve_execution_profile("hybrid")
        self.assertIn("api.openai", profile.optional_adapters)
        self.assertNotIn("api.openai", profile.required_adapters)
