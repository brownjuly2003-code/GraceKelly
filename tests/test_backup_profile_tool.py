from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path

from gracekelly.tools.backup_profile import backup_profile, collect_files, resolve_profile_dir


class CollectFilesTests(unittest.TestCase):
    def test_picks_up_known_cookie_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp)
            (profile / "Cookies").write_bytes(b"cookie-bytes")
            (profile / "Local State").write_text('{"x":1}')
            (profile / "History").write_text("ignored")
            found = collect_files(profile)
            names = sorted(item.name for item in found)
            self.assertIn("Cookies", names)
            self.assertIn("Local State", names)
            self.assertNotIn("History", names)

    def test_empty_profile_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(collect_files(Path(temp)), [])


class ResolveProfileDirTests(unittest.TestCase):
    def test_cli_value_takes_precedence(self) -> None:
        self.assertEqual(resolve_profile_dir("/explicit/path"), "/explicit/path")

    def test_empty_raises(self) -> None:
        import os
        original = os.environ.pop("GRACEKELLY_BROWSER_PROFILE_DIR", None)
        try:
            with self.assertRaises(ValueError):
                resolve_profile_dir(None)
        finally:
            if original is not None:
                os.environ["GRACEKELLY_BROWSER_PROFILE_DIR"] = original


class BackupProfileTests(unittest.TestCase):
    def test_creates_tar_gz_with_cookie_files(self) -> None:
        with tempfile.TemporaryDirectory() as src_temp, tempfile.TemporaryDirectory() as out_temp:
            profile = Path(src_temp)
            (profile / "Cookies").write_bytes(b"cookie-bytes")
            (profile / "Local State").write_text('{"state":1}')
            archive = backup_profile(str(profile), out_temp)
            self.assertTrue(archive.exists())
            self.assertTrue(archive.name.endswith(".tar.gz"))
            with tarfile.open(archive, "r:gz") as tar:
                members = [member.name for member in tar.getmembers()]
            self.assertTrue(any(name.endswith("Cookies") for name in members))
            self.assertTrue(any(name.endswith("Local State") for name in members))

    def test_missing_profile_raises(self) -> None:
        with tempfile.TemporaryDirectory() as out_temp:
            with self.assertRaises(FileNotFoundError):
                backup_profile("/nonexistent/path/xyz", out_temp)

    def test_empty_profile_raises(self) -> None:
        with tempfile.TemporaryDirectory() as src_temp, tempfile.TemporaryDirectory() as out_temp:
            with self.assertRaises(RuntimeError) as ctx:
                backup_profile(src_temp, out_temp)
            self.assertIn("No recognised", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
