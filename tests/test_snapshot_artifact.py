from __future__ import annotations

import pathlib
import tempfile
import unittest

from gracekelly.tools.snapshot_artifact import (
    artifact_metadata,
    checksum_status,
    derived_missing_task_ids,
    derived_task_count,
    exported_task_ids,
    exported_task_ids_status,
    format_status,
    has_task_list,
    import_ready,
    manifest_count,
    manifest_count_status,
    manifest_status,
    migration_status,
    missing_task_ids,
    missing_task_ids_status,
    selection_status,
    snapshot_status_consistency_status,
    validate_manifest,
)
from gracekelly.tools.snapshot_digest import SNAPSHOT_FORMAT_VERSION, compute_snapshot_sha256

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_bundle(task_id: str, *, steps: int = 1, events: int = 1) -> dict:  # type: ignore[type-arg]
    return {
        "task": {"task_id": task_id},
        "steps": [{}] * steps,
        "events": [{}] * events,
    }


def _full_snapshot(task_ids: list[str]) -> dict:  # type: ignore[type-arg]
    """Build a self-consistent snapshot for the given task IDs."""
    tasks = [_task_bundle(tid, steps=2, events=3) for tid in task_ids]
    snap: dict = {  # type: ignore[type-arg]
        "snapshot_format_version": SNAPSHOT_FORMAT_VERSION,
        "migration": "0002_add_retry_of_task_id",
        "tasks": tasks,
        "task_count": len(tasks),
        "step_count": len(tasks) * 2,
        "event_count": len(tasks) * 3,
        "exported_task_ids": task_ids,
        "missing_task_ids": [],
        "status": "ok",
        "selection": {"task_ids": task_ids, "limit": None} if task_ids else {"task_ids": [], "limit": 10},
    }
    snap["snapshot_sha256"] = compute_snapshot_sha256(snap)
    return snap


# ---------------------------------------------------------------------------
# artifact_metadata
# ---------------------------------------------------------------------------

class ArtifactMetadataTests(unittest.TestCase):
    def test_existing_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            meta = artifact_metadata(pathlib.Path(f.name))
        self.assertTrue(meta["exists"])
        self.assertFalse(meta["compressed"])

    def test_existing_gz_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".gz") as f:
            meta = artifact_metadata(pathlib.Path(f.name))
        self.assertTrue(meta["compressed"])

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            artifact_metadata(pathlib.Path("/nonexistent/path.json"))

    def test_missing_file_allow_missing(self) -> None:
        meta = artifact_metadata(pathlib.Path("/nonexistent/path.json"), allow_missing=True)
        self.assertFalse(meta["exists"])
        self.assertIsNone(meta["size_bytes"])

    def test_existing_file_size_nonnegative(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            meta = artifact_metadata(pathlib.Path(f.name))
        size_bytes = meta["size_bytes"]
        assert isinstance(size_bytes, int)
        self.assertGreaterEqual(size_bytes, 0)


# ---------------------------------------------------------------------------
# checksum_status
# ---------------------------------------------------------------------------

class ChecksumStatusTests(unittest.TestCase):
    def test_verified(self) -> None:
        snap: dict[str, object] = {"a": 1}
        snap["snapshot_sha256"] = compute_snapshot_sha256(snap)
        state, expected, computed = checksum_status(snap)
        self.assertEqual(state, "verified")
        self.assertEqual(expected, computed)

    def test_missing(self) -> None:
        snap: dict[str, object] = {"a": 1}
        state, expected, _ = checksum_status(snap)
        self.assertEqual(state, "missing")
        self.assertIsNone(expected)

    def test_mismatch(self) -> None:
        snap: dict[str, object] = {"a": 1, "snapshot_sha256": "wrong_hash"}
        state, expected, computed = checksum_status(snap)
        self.assertEqual(state, "mismatch")
        self.assertEqual(expected, "wrong_hash")
        self.assertNotEqual(expected, computed)


# ---------------------------------------------------------------------------
# format_status / migration_status
# ---------------------------------------------------------------------------

class FormatStatusTests(unittest.TestCase):
    def test_current(self) -> None:
        snap = {"snapshot_format_version": SNAPSHOT_FORMAT_VERSION}
        self.assertEqual(format_status(snap, supported_snapshot_format_version=SNAPSHOT_FORMAT_VERSION), "current")

    def test_mismatch(self) -> None:
        snap = {"snapshot_format_version": 99}
        self.assertEqual(format_status(snap, supported_snapshot_format_version=SNAPSHOT_FORMAT_VERSION), "mismatch")

    def test_unknown(self) -> None:
        self.assertEqual(format_status({}, supported_snapshot_format_version=SNAPSHOT_FORMAT_VERSION), "unknown")


class MigrationStatusTests(unittest.TestCase):
    def test_current(self) -> None:
        snap = {"migration": "0002_add_retry"}
        self.assertEqual(migration_status(snap, supported_migration="0002_add_retry"), "current")

    def test_mismatch(self) -> None:
        snap = {"migration": "0001_init"}
        self.assertEqual(migration_status(snap, supported_migration="0002_add_retry"), "mismatch")

    def test_unknown(self) -> None:
        self.assertEqual(migration_status({}, supported_migration="0002_add_retry"), "unknown")


# ---------------------------------------------------------------------------
# has_task_list / derived_task_count / exported_task_ids
# ---------------------------------------------------------------------------

class HasTaskListTests(unittest.TestCase):
    def test_list_present(self) -> None:
        self.assertTrue(has_task_list({"tasks": []}))

    def test_not_a_list(self) -> None:
        self.assertFalse(has_task_list({"tasks": "nope"}))

    def test_missing(self) -> None:
        self.assertFalse(has_task_list({}))


class DerivedTaskCountTests(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(derived_task_count({"tasks": []}), 0)

    def test_two_tasks(self) -> None:
        snap = {"tasks": [_task_bundle("t1"), _task_bundle("t2")]}
        self.assertEqual(derived_task_count(snap), 2)

    def test_no_tasks_key(self) -> None:
        self.assertEqual(derived_task_count({}), 0)


class ExportedTaskIdsTests(unittest.TestCase):
    def test_explicit_ids_returned(self) -> None:
        snap = {"exported_task_ids": ["a", "b"], "tasks": []}
        self.assertEqual(exported_task_ids(snap), ["a", "b"])

    def test_derived_from_bundles(self) -> None:
        snap = {"tasks": [_task_bundle("x1"), _task_bundle("x2")]}
        self.assertEqual(exported_task_ids(snap), ["x1", "x2"])

    def test_empty_tasks(self) -> None:
        self.assertEqual(exported_task_ids({"tasks": []}), [])

    def test_no_tasks_key(self) -> None:
        self.assertEqual(exported_task_ids({}), [])


# ---------------------------------------------------------------------------
# manifest_count / manifest_count_status
# ---------------------------------------------------------------------------

class ManifestCountTests(unittest.TestCase):
    def test_explicit_count(self) -> None:
        self.assertEqual(manifest_count({"task_count": 5}, "task_count"), 5)

    def test_derived_task_count(self) -> None:
        snap = {"tasks": [_task_bundle("t1"), _task_bundle("t2")]}
        self.assertEqual(manifest_count(snap, "task_count"), 2)

    def test_derived_step_count(self) -> None:
        snap = {"tasks": [_task_bundle("t1", steps=3)]}
        self.assertEqual(manifest_count(snap, "step_count"), 3)

    def test_derived_event_count(self) -> None:
        snap = {"tasks": [_task_bundle("t1", events=4)]}
        self.assertEqual(manifest_count(snap, "event_count"), 4)


class ManifestCountStatusTests(unittest.TestCase):
    def test_verified(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "task_count": 1}
        self.assertEqual(manifest_count_status(snap, "task_count"), "verified")

    def test_derived_when_no_explicit(self) -> None:
        snap = {"tasks": [_task_bundle("t1")]}
        self.assertEqual(manifest_count_status(snap, "task_count"), "derived")

    def test_mismatch_wrong_count(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "task_count": 99}
        self.assertEqual(manifest_count_status(snap, "task_count"), "mismatch")

    def test_mismatch_no_task_list(self) -> None:
        snap = {"task_count": 1}
        self.assertEqual(manifest_count_status(snap, "task_count"), "mismatch")


# ---------------------------------------------------------------------------
# manifest_status / snapshot_status_consistency_status
# ---------------------------------------------------------------------------

class ManifestStatusTests(unittest.TestCase):
    def test_verified_on_full_consistent_snapshot(self) -> None:
        snap = _full_snapshot(["t1", "t2"])
        self.assertEqual(manifest_status(snap), "verified")

    def test_mismatch_on_wrong_task_count(self) -> None:
        snap = _full_snapshot(["t1"])
        snap["task_count"] = 99
        self.assertEqual(manifest_status(snap), "mismatch")

    def test_mismatch_on_no_task_list(self) -> None:
        self.assertEqual(manifest_status({}), "mismatch")


class SnapshotStatusConsistencyStatusTests(unittest.TestCase):
    def test_verified_ok(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "selection": {"task_ids": ["t1"]},
            "status": "ok",
        }
        self.assertEqual(snapshot_status_consistency_status(snap), "verified")

    def test_verified_partial(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "selection": {"task_ids": ["t1", "t2"]},
            "status": "partial",
        }
        self.assertEqual(snapshot_status_consistency_status(snap), "verified")

    def test_mismatch_wrong_status(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "selection": {"task_ids": ["t1"]},
            "status": "partial",
        }
        self.assertEqual(snapshot_status_consistency_status(snap), "mismatch")

    def test_missing_status_field(self) -> None:
        snap: dict = {}  # type: ignore[type-arg]
        self.assertEqual(snapshot_status_consistency_status(snap), "missing")


# ---------------------------------------------------------------------------
# exported_task_ids_status / missing_task_ids / missing_task_ids_status
# ---------------------------------------------------------------------------

class ExportedTaskIdsStatusTests(unittest.TestCase):
    def test_verified(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "exported_task_ids": ["t1"]}
        self.assertEqual(exported_task_ids_status(snap), "verified")

    def test_derived(self) -> None:
        snap = {"tasks": [_task_bundle("t1")]}
        self.assertEqual(exported_task_ids_status(snap), "derived")

    def test_mismatch_wrong_ids(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "exported_task_ids": ["t2"]}
        self.assertEqual(exported_task_ids_status(snap), "mismatch")


class MissingTaskIdsTests(unittest.TestCase):
    def test_explicit_missing_ids(self) -> None:
        snap = {"missing_task_ids": ["m1", "m2"], "tasks": []}
        self.assertEqual(missing_task_ids(snap), ["m1", "m2"])

    def test_derived_missing_ids(self) -> None:
        snap = {
            "selection": {"task_ids": ["t1", "t2"]},
            "tasks": [_task_bundle("t1")],
        }
        result = missing_task_ids(snap)
        self.assertIn("t2", result)

    def test_no_missing(self) -> None:
        snap = {
            "selection": {"task_ids": ["t1"]},
            "tasks": [_task_bundle("t1")],
        }
        self.assertEqual(missing_task_ids(snap), [])


class MissingTaskIdsStatusTests(unittest.TestCase):
    def test_verified(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "missing_task_ids": [], "selection": {"task_ids": ["t1"]}}
        self.assertEqual(missing_task_ids_status(snap), "verified")

    def test_derived(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "selection": {"task_ids": ["t1"]}}
        self.assertEqual(missing_task_ids_status(snap), "derived")

    def test_mismatch_no_tasks(self) -> None:
        self.assertEqual(missing_task_ids_status({}), "mismatch")


# ---------------------------------------------------------------------------
# selection_status / manifest_status
# ---------------------------------------------------------------------------

class SelectionStatusTests(unittest.TestCase):
    def test_missing(self) -> None:
        self.assertEqual(selection_status({}), "missing")

    def test_task_ids_verified(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "exported_task_ids": ["t1"],
            "missing_task_ids": [],
            "selection": {"task_ids": ["t1"]},
        }
        self.assertEqual(selection_status(snap), "verified")

    def test_limit_verified_within_budget(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "task_count": 1,
            "selection": {"task_ids": [], "limit": 10},
        }
        self.assertEqual(selection_status(snap), "verified")

    def test_limit_mismatch_exceeds_budget(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1"), _task_bundle("t2")],
            "task_count": 2,
            "selection": {"task_ids": [], "limit": 1},
        }
        self.assertEqual(selection_status(snap), "mismatch")


# ---------------------------------------------------------------------------
# import_ready / validate_manifest
# ---------------------------------------------------------------------------

class ImportReadyTests(unittest.TestCase):
    def test_full_valid_snapshot_is_ready(self) -> None:
        snap = _full_snapshot(["t1", "t2"])
        self.assertTrue(
            import_ready(
                snap,
                supported_snapshot_format_version=SNAPSHOT_FORMAT_VERSION,
                supported_migration="0002_add_retry_of_task_id",
            )
        )

    def test_wrong_checksum_not_ready(self) -> None:
        snap = _full_snapshot(["t1"])
        snap["snapshot_sha256"] = "wrong"
        self.assertFalse(
            import_ready(
                snap,
                supported_snapshot_format_version=SNAPSHOT_FORMAT_VERSION,
                supported_migration="0002_add_retry_of_task_id",
            )
        )

    def test_wrong_format_version_not_ready(self) -> None:
        snap = _full_snapshot(["t1"])
        snap["snapshot_format_version"] = 99
        snap["snapshot_sha256"] = compute_snapshot_sha256(snap)
        self.assertFalse(
            import_ready(
                snap,
                supported_snapshot_format_version=SNAPSHOT_FORMAT_VERSION,
                supported_migration="0002_add_retry_of_task_id",
            )
        )


class ValidateManifestTests(unittest.TestCase):
    def test_valid_snapshot_no_error(self) -> None:
        snap = _full_snapshot(["t1", "t2"])
        validate_manifest(snap)  # should not raise

    def test_wrong_task_count_raises(self) -> None:
        snap = _full_snapshot(["t1"])
        snap["task_count"] = 99
        with self.assertRaises(ValueError):
            validate_manifest(snap)

    def test_wrong_exported_ids_raises(self) -> None:
        snap = _full_snapshot(["t1"])
        snap["exported_task_ids"] = ["wrong"]
        with self.assertRaises(ValueError):
            validate_manifest(snap)


# ---------------------------------------------------------------------------
# derived_missing_task_ids
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Edge cases: malformed snapshot data
# ---------------------------------------------------------------------------

class ExportedTaskIdsMalformedTests(unittest.TestCase):
    def test_task_item_not_dict_skipped(self) -> None:
        snap = {"tasks": [_task_bundle("t1"), "not_a_dict", None]}
        ids = exported_task_ids(snap)
        self.assertEqual(ids, ["t1"])

    def test_task_payload_not_dict_skipped(self) -> None:
        snap = {"tasks": [{"task": "not_a_dict"}, _task_bundle("t2")]}
        ids = exported_task_ids(snap)
        self.assertEqual(ids, ["t2"])


class DerivedNestedCountMalformedTests(unittest.TestCase):
    def test_non_dict_task_items_skipped(self) -> None:
        from gracekelly.tools.snapshot_artifact import derived_nested_count

        snap = {"tasks": [_task_bundle("t1", steps=2), "bad_item", 42]}
        self.assertEqual(derived_nested_count(snap, "step_count"), 2)


class ManifestCountStatusEdgeTests(unittest.TestCase):
    def test_non_int_explicit_count_returns_mismatch(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "task_count": "not_int"}
        self.assertEqual(manifest_count_status(snap, "task_count"), "mismatch")


class ExportedTaskIdsStatusEdgeTests(unittest.TestCase):
    def test_non_list_explicit_ids_returns_mismatch(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "exported_task_ids": "not_a_list"}
        self.assertEqual(exported_task_ids_status(snap), "mismatch")


class MissingTaskIdsStatusEdgeTests(unittest.TestCase):
    def test_non_list_explicit_ids_returns_mismatch(self) -> None:
        snap = {"tasks": [_task_bundle("t1")], "missing_task_ids": "not_a_list"}
        self.assertEqual(missing_task_ids_status(snap), "mismatch")


class SnapshotStatusConsistencyEdgeTests(unittest.TestCase):
    def test_non_string_status_returns_mismatch(self) -> None:
        snap = {"status": 42}
        self.assertEqual(snapshot_status_consistency_status(snap), "mismatch")


class SelectionStatusEdgeTests(unittest.TestCase):
    def test_non_dict_selection_returns_mismatch(self) -> None:
        self.assertEqual(selection_status({"selection": "bad"}), "mismatch")

    def test_non_list_task_ids_returns_mismatch(self) -> None:
        self.assertEqual(selection_status({"selection": {"task_ids": "bad"}}), "mismatch")

    def test_non_string_task_id_item_returns_mismatch(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "selection": {"task_ids": [123]},
        }
        self.assertEqual(selection_status(snap), "mismatch")

    def test_task_ids_with_limit_returns_mismatch(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "exported_task_ids": ["t1"],
            "missing_task_ids": [],
            "selection": {"task_ids": ["t1"], "limit": 10},
        }
        self.assertEqual(selection_status(snap), "mismatch")

    def test_invalid_limit_type_returns_mismatch(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "task_count": 1,
            "selection": {"task_ids": [], "limit": "bad"},
        }
        self.assertEqual(selection_status(snap), "mismatch")

    def test_limit_zero_returns_mismatch(self) -> None:
        snap = {
            "tasks": [_task_bundle("t1")],
            "task_count": 1,
            "selection": {"task_ids": [], "limit": 0},
        }
        self.assertEqual(selection_status(snap), "mismatch")


class DerivedMissingTaskIdsMalformedTests(unittest.TestCase):
    def test_non_dict_selection_returns_empty(self) -> None:
        self.assertEqual(derived_missing_task_ids({"selection": "bad"}), [])

    def test_non_list_task_ids_returns_empty(self) -> None:
        self.assertEqual(derived_missing_task_ids({"selection": {"task_ids": "bad"}}), [])


class DerivedMissingTaskIdsTests(unittest.TestCase):
    def test_all_present(self) -> None:
        snap = {
            "selection": {"task_ids": ["t1", "t2"]},
            "tasks": [_task_bundle("t1"), _task_bundle("t2")],
        }
        self.assertEqual(derived_missing_task_ids(snap), [])

    def test_some_missing(self) -> None:
        snap = {
            "selection": {"task_ids": ["t1", "t2", "t3"]},
            "tasks": [_task_bundle("t1")],
        }
        missing = derived_missing_task_ids(snap)
        self.assertIn("t2", missing)
        self.assertIn("t3", missing)

    def test_no_selection(self) -> None:
        snap = {"tasks": [_task_bundle("t1")]}
        self.assertEqual(derived_missing_task_ids(snap), [])


if __name__ == "__main__":
    unittest.main()
