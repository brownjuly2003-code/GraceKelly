from __future__ import annotations

import pathlib
import shutil
import tempfile
import unittest

from gracekelly.tools.snapshot_io import read_snapshot_text, write_snapshot_text

TMP_ROOT = pathlib.Path(".workflow/tmp-tests")
TMP_ROOT.mkdir(parents=True, exist_ok=True)


class ReadSnapshotTextTests(unittest.TestCase):
    def test_reads_plain_text_file(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", encoding="utf-8", delete=False, dir=TMP_ROOT,
        ) as f:
            f.write('{"hello": "world"}')
            path = pathlib.Path(f.name)
        try:
            self.assertEqual(read_snapshot_text(path), '{"hello": "world"}')
        finally:
            path.unlink(missing_ok=True)

    def test_reads_gzip_file(self) -> None:
        import gzip
        with tempfile.NamedTemporaryFile(suffix=".gz", delete=False, dir=TMP_ROOT) as f:
            path = pathlib.Path(f.name)
        try:
            with gzip.open(path, "wt", encoding="utf-8") as gz:
                gz.write("compressed content")
            self.assertEqual(read_snapshot_text(path), "compressed content")
        finally:
            path.unlink(missing_ok=True)

    def test_reads_unicode(self) -> None:
        content = "Привет мир 🌍"
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", encoding="utf-8", delete=False, dir=TMP_ROOT,
        ) as f:
            f.write(content)
            path = pathlib.Path(f.name)
        try:
            self.assertEqual(read_snapshot_text(path), content)
        finally:
            path.unlink(missing_ok=True)


class WriteSnapshotTextTests(unittest.TestCase):
    def test_writes_plain_text_file(self) -> None:
        path = TMP_ROOT / "write-plain.json"
        path.unlink(missing_ok=True)
        try:
            write_snapshot_text(path, '{"a": 1}')
            self.assertEqual(path.read_text(encoding="utf-8"), '{"a": 1}')
        finally:
            path.unlink(missing_ok=True)

    def test_writes_gzip_file(self) -> None:
        import gzip
        path = TMP_ROOT / "write-gzip.json.gz"
        path.unlink(missing_ok=True)
        try:
            write_snapshot_text(path, "compressed output")
            with gzip.open(path, "rt", encoding="utf-8") as gz:
                self.assertEqual(gz.read(), "compressed output")
        finally:
            path.unlink(missing_ok=True)

    def test_creates_parent_directories(self) -> None:
        nested_root = TMP_ROOT / "deep"
        shutil.rmtree(nested_root, ignore_errors=True)
        path = nested_root / "nested" / "out.json"
        try:
            write_snapshot_text(path, "content")
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "content")
        finally:
            shutil.rmtree(nested_root, ignore_errors=True)

    def test_overwrites_existing_file(self) -> None:
        path = TMP_ROOT / "overwrite.json"
        path.unlink(missing_ok=True)
        try:
            write_snapshot_text(path, "first")
            write_snapshot_text(path, "second")
            self.assertEqual(path.read_text(encoding="utf-8"), "second")
        finally:
            path.unlink(missing_ok=True)

    def test_writes_unicode(self) -> None:
        content = "Юникод 💾"
        path = TMP_ROOT / "write-unicode.json"
        path.unlink(missing_ok=True)
        try:
            write_snapshot_text(path, content)
            self.assertEqual(path.read_text(encoding="utf-8"), content)
        finally:
            path.unlink(missing_ok=True)


class RoundTripTests(unittest.TestCase):
    def test_plain_roundtrip(self) -> None:
        content = '{"tasks": [], "version": 1}'
        path = TMP_ROOT / "roundtrip.json"
        path.unlink(missing_ok=True)
        try:
            write_snapshot_text(path, content)
            self.assertEqual(read_snapshot_text(path), content)
        finally:
            path.unlink(missing_ok=True)

    def test_gzip_roundtrip(self) -> None:
        content = '{"tasks": [], "version": 1}'
        path = TMP_ROOT / "roundtrip.json.gz"
        path.unlink(missing_ok=True)
        try:
            write_snapshot_text(path, content)
            self.assertEqual(read_snapshot_text(path), content)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
