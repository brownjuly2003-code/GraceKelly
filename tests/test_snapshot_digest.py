from __future__ import annotations

import hashlib
import json
import unittest

from gracekelly.tools.snapshot_digest import compute_snapshot_sha256, snapshot_without_digest


class SnapshotWithoutDigestTests(unittest.TestCase):
    def test_removes_snapshot_sha256_key(self) -> None:
        snap = {"a": 1, "snapshot_sha256": "abc123", "b": 2}
        result = snapshot_without_digest(snap)
        self.assertNotIn("snapshot_sha256", result)

    def test_preserves_other_keys(self) -> None:
        snap = {"a": 1, "snapshot_sha256": "abc", "b": [1, 2]}
        result = snapshot_without_digest(snap)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], [1, 2])

    def test_no_sha256_key_unchanged(self) -> None:
        snap = {"tasks": [], "version": 1}
        result = snapshot_without_digest(snap)
        self.assertEqual(result, snap)

    def test_returns_new_dict(self) -> None:
        snap = {"x": 1, "snapshot_sha256": "z"}
        result = snapshot_without_digest(snap)
        self.assertIsNot(result, snap)

    def test_empty_snapshot(self) -> None:
        self.assertEqual(snapshot_without_digest({}), {})


class ComputeSnapshotSha256Tests(unittest.TestCase):
    def _manual_digest(self, snap: dict) -> str:  # type: ignore[type-arg]
        """Reference implementation matching the production code."""
        without = {k: v for k, v in snap.items() if k != "snapshot_sha256"}
        encoded = json.dumps(without, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def test_deterministic(self) -> None:
        snap = {"tasks": [], "version": 1, "status": "ok"}
        self.assertEqual(compute_snapshot_sha256(snap), compute_snapshot_sha256(snap))

    def test_matches_manual_reference(self) -> None:
        snap = {"tasks": [{"id": "t1"}], "task_count": 1}
        self.assertEqual(compute_snapshot_sha256(snap), self._manual_digest(snap))

    def test_ignores_existing_sha256_field(self) -> None:
        snap = {"a": 1}
        snap_with_hash = {"a": 1, "snapshot_sha256": "old_hash"}
        self.assertEqual(compute_snapshot_sha256(snap), compute_snapshot_sha256(snap_with_hash))

    def test_different_content_different_hash(self) -> None:
        snap1 = {"a": 1}
        snap2 = {"a": 2}
        self.assertNotEqual(compute_snapshot_sha256(snap1), compute_snapshot_sha256(snap2))

    def test_returns_64_char_hex_string(self) -> None:
        digest = compute_snapshot_sha256({"x": 1})
        self.assertEqual(len(digest), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in digest))

    def test_empty_snapshot(self) -> None:
        digest = compute_snapshot_sha256({})
        self.assertEqual(len(digest), 64)

    def test_key_order_does_not_matter(self) -> None:
        snap1 = {"b": 2, "a": 1}
        snap2 = {"a": 1, "b": 2}
        self.assertEqual(compute_snapshot_sha256(snap1), compute_snapshot_sha256(snap2))


if __name__ == "__main__":
    unittest.main()
