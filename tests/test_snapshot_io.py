from __future__ import annotations

import pathlib
import tempfile
import unittest

from gracekelly.tools.snapshot_io import read_snapshot_text, write_snapshot_text


class ReadSnapshotTextTests(unittest.TestCase):
    def test_reads_plain_text_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", encoding="utf-8", delete=False) as f:
            f.write('{"hello": "world"}')
            path = pathlib.Path(f.name)
        try:
            self.assertEqual(read_snapshot_text(path), '{"hello": "world"}')
        finally:
            path.unlink(missing_ok=True)

    def test_reads_gzip_file(self) -> None:
        import gzip
        with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as f:
            path = pathlib.Path(f.name)
        try:
            with gzip.open(path, "wt", encoding="utf-8") as gz:
                gz.write("compressed content")
            self.assertEqual(read_snapshot_text(path), "compressed content")
        finally:
            path.unlink(missing_ok=True)

    def test_reads_unicode(self) -> None:
        content = "Привет мир 🌍"
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", encoding="utf-8", delete=False) as f:
            f.write(content)
            path = pathlib.Path(f.name)
        try:
            self.assertEqual(read_snapshot_text(path), content)
        finally:
            path.unlink(missing_ok=True)


class WriteSnapshotTextTests(unittest.TestCase):
    def test_writes_plain_text_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "out.json"
            write_snapshot_text(path, '{"a": 1}')
            self.assertEqual(path.read_text(encoding="utf-8"), '{"a": 1}')

    def test_writes_gzip_file(self) -> None:
        import gzip
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "out.json.gz"
            write_snapshot_text(path, "compressed output")
            with gzip.open(path, "rt", encoding="utf-8") as gz:
                self.assertEqual(gz.read(), "compressed output")

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "deep" / "nested" / "out.json"
            write_snapshot_text(path, "content")
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "content")

    def test_overwrites_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "out.json"
            write_snapshot_text(path, "first")
            write_snapshot_text(path, "second")
            self.assertEqual(path.read_text(encoding="utf-8"), "second")

    def test_writes_unicode(self) -> None:
        content = "Юникод 💾"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "out.json"
            write_snapshot_text(path, content)
            self.assertEqual(path.read_text(encoding="utf-8"), content)


class RoundTripTests(unittest.TestCase):
    def test_plain_roundtrip(self) -> None:
        content = '{"tasks": [], "version": 1}'
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "snap.json"
            write_snapshot_text(path, content)
            self.assertEqual(read_snapshot_text(path), content)

    def test_gzip_roundtrip(self) -> None:
        content = '{"tasks": [], "version": 1}'
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "snap.json.gz"
            write_snapshot_text(path, content)
            self.assertEqual(read_snapshot_text(path), content)


if __name__ == "__main__":
    unittest.main()
