from __future__ import annotations

import json
import pathlib
import tempfile
import unittest
from typing import Any
from unittest.mock import patch

from gracekelly.tools.recon_weekly import (
    BASELINE_NAME,
    DRIFT_FLAG_NAME,
    LATEST_NAME,
    main,
    run_recon,
)


def _make_capture(
    *,
    buttons: list[str],
    models: list[str],
    files: dict[str, str] | None = None,
    direct_model_button_visible: bool = True,
    more_button_visible: bool = False,
    more_clicked: bool = False,
) -> Any:
    artefact_files = {"home_screenshot": "recon-01-home.png", **(files or {})}

    def _capture(
        *,
        profile_dir: str,
        output_dir: str,
        base_url: str,
        channel: str,
        **_: object,
    ) -> dict[str, Any]:
        outdir = pathlib.Path(output_dir)
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "recon-01-buttons.json").write_text(json.dumps(buttons), encoding="utf-8")
        (outdir / "recon-03-model-menu.json").write_text(json.dumps(models), encoding="utf-8")
        manifest = {
            "direct_model_button_visible": direct_model_button_visible,
            "more_button_visible": more_button_visible,
            "more_clicked": more_clicked,
            "files": artefact_files,
        }
        (outdir / "recon-99-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    return _capture


class ReconWeeklyBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = pathlib.Path(self._tmp.name)
        self.state_dir = self.tmp_root / "state"
        self.drift_log = self.tmp_root / "logs" / "recon-drift.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_first_run_creates_baseline_no_drift_artefacts(self) -> None:
        capture = _make_capture(buttons=["New thread"], models=["Sonar", "Claude"])
        rc = run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=capture,
        )
        self.assertEqual(rc, 0)
        self.assertTrue((self.state_dir / BASELINE_NAME).exists())
        self.assertTrue((self.state_dir / LATEST_NAME).exists())
        self.assertFalse((self.state_dir / DRIFT_FLAG_NAME).exists())
        self.assertFalse(self.drift_log.exists())

    def test_baseline_payload_is_normalised_snapshot(self) -> None:
        capture = _make_capture(buttons=["B", "A"], models=["Z", "A"])
        run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=capture,
        )
        baseline = json.loads((self.state_dir / BASELINE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(baseline["home_buttons"], ["A", "B"])
        self.assertEqual(baseline["model_menu"], ["A", "Z"])
        self.assertIn("flags", baseline)
        self.assertIn("artefact_files", baseline)


class ReconWeeklyDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = pathlib.Path(self._tmp.name)
        self.state_dir = self.tmp_root / "state"
        self.drift_log = self.tmp_root / "logs" / "recon-drift.jsonl"
        # establish baseline
        capture_baseline = _make_capture(buttons=["New thread"], models=["Sonar", "Claude"])
        run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=capture_baseline,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_no_diff_exit_zero_no_artefacts_added(self) -> None:
        capture = _make_capture(buttons=["New thread"], models=["Sonar", "Claude"])
        rc = run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=capture,
        )
        self.assertEqual(rc, 0)
        self.assertFalse((self.state_dir / DRIFT_FLAG_NAME).exists())
        self.assertFalse(self.drift_log.exists())

    def test_drift_in_models_writes_flag_and_jsonl_exit_one(self) -> None:
        capture = _make_capture(buttons=["New thread"], models=["Sonar", "Claude", "Gemini"])
        rc = run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=capture,
        )
        self.assertEqual(rc, 1)
        flag_path = self.state_dir / DRIFT_FLAG_NAME
        self.assertTrue(flag_path.exists())
        flag_payload = json.loads(flag_path.read_text(encoding="utf-8"))
        self.assertIn("model_menu", flag_payload["changed"])
        self.assertEqual(flag_payload["added"], [])
        self.assertEqual(flag_payload["removed"], [])
        lines = self.drift_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        line_payload = json.loads(lines[0])
        self.assertIn("ts", line_payload)
        self.assertEqual(line_payload["changed"], ["model_menu"])

    def test_drift_in_flags_detected(self) -> None:
        capture = _make_capture(
            buttons=["New thread"],
            models=["Sonar", "Claude"],
            direct_model_button_visible=False,
            more_button_visible=True,
            more_clicked=True,
        )
        rc = run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=capture,
        )
        self.assertEqual(rc, 1)
        flag_payload = json.loads((self.state_dir / DRIFT_FLAG_NAME).read_text(encoding="utf-8"))
        self.assertIn("flags", flag_payload["changed"])

    def test_drift_when_home_menu_button_count_increases(self) -> None:
        capture = _make_capture(
            buttons=["New thread", "Search::Search"],
            models=["Sonar", "Claude"],
        )
        rc = run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=capture,
        )
        self.assertEqual(rc, 1)
        flag_payload = json.loads((self.state_dir / DRIFT_FLAG_NAME).read_text(encoding="utf-8"))
        self.assertIn("home_menu_button_count", flag_payload["changed"])

    def test_flag_removed_when_drift_resolves(self) -> None:
        # introduce drift
        drifty = _make_capture(buttons=["New thread"], models=["Sonar", "Claude", "Gemini"])
        run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=drifty,
        )
        flag_path = self.state_dir / DRIFT_FLAG_NAME
        self.assertTrue(flag_path.exists())
        # restore baseline payload
        restored = _make_capture(buttons=["New thread"], models=["Sonar", "Claude"])
        rc = run_recon(
            profile_dir="x",
            state_dir=self.state_dir,
            drift_log_path=self.drift_log,
            capture_func=restored,
        )
        self.assertEqual(rc, 0)
        self.assertFalse(flag_path.exists())

    def test_drift_log_appends_does_not_overwrite(self) -> None:
        for models in (["Sonar", "Claude", "Gemini"], ["Sonar", "Claude", "Gemini", "Kimi"]):
            capture = _make_capture(buttons=["New thread"], models=models)
            run_recon(
                profile_dir="x",
                state_dir=self.state_dir,
                drift_log_path=self.drift_log,
                capture_func=capture,
            )
        lines = self.drift_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)


class ReconWeeklyMainTests(unittest.TestCase):
    def test_env_file_profile_dir_used_by_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = pathlib.Path(tmp)
            (tmp_root / ".env").write_text(
                "GRACEKELLY_BROWSER_PROFILE_DIR=C:/Profiles/Scheduled\n",
                encoding="utf-8",
            )
            with (
                patch("gracekelly.tools.recon_weekly.REPO_ROOT", tmp_root),
                patch("gracekelly.tools.recon_weekly.run_recon", return_value=0) as run_mock,
                patch.dict("os.environ", {}, clear=True),
            ):
                rc = main(argv=[])

        self.assertEqual(rc, 0)
        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.kwargs["profile_dir"], "C:/Profiles/Scheduled")

    def test_missing_profile_dir_returns_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("gracekelly.tools.recon_weekly.REPO_ROOT", pathlib.Path(tmp)),
                patch.dict("os.environ", {}, clear=True),
            ):
                rc = main(argv=["--base-url", "https://example.com"])
        self.assertEqual(rc, 2)
