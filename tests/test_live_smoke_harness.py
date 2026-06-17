from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

module_path = Path(__file__).resolve().parents[1] / "scripts" / "live_smart_smoke.py"
spec = importlib.util.spec_from_file_location("live_smart_smoke", module_path)
assert spec is not None
assert spec.loader is not None
live_smart_smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_smart_smoke)

SMART_ANSWER = ("Europe China USA adoption subsidies EV markets remain highly dynamic. " * 10).strip()
CONSENSUS_ANSWER = ("электромобиль производитель в Китае China лидирует на рынке. " * 8).strip()
UPLOAD_ANSWER = ("Attachment summary with key points and concise file overview. " * 4).strip()
NON_TOPIC_SMART_ANSWER = ("Battery factories and charging networks keep growing globally. " * 10).strip()


def test_evaluate_accepts_valid_smart_response() -> None:
    ok, reasons = live_smart_smoke.evaluate(
        {"status_code": 200, "body_json": {"answer": SMART_ANSWER}},
        "smart",
    )

    assert ok is True
    assert reasons == []


def test_evaluate_rejects_too_short_answer() -> None:
    ok, reasons = live_smart_smoke.evaluate(
        {"status_code": 200, "body_json": {"answer": "x" * 100}},
        "smart",
    )

    assert ok is False
    assert any("answer too short" in reason for reason in reasons)


def test_evaluate_rejects_forbidden_marker() -> None:
    ok, reasons = live_smart_smoke.evaluate(
        {"status_code": 200, "body_json": {"answer": f"{SMART_ANSWER} Ask a follow-up"}},
        "smart",
    )

    assert ok is False
    assert any("forbidden marker" in reason for reason in reasons)


def test_evaluate_rejects_missing_topic_keywords_for_smart() -> None:
    ok, reasons = live_smart_smoke.evaluate(
        {"status_code": 200, "body_json": {"answer": NON_TOPIC_SMART_ANSWER}},
        "smart",
    )

    assert ok is False
    assert any("no topic keyword" in reason for reason in reasons)


def test_evaluate_accepts_consensus_with_new_keywords() -> None:
    ok, reasons = live_smart_smoke.evaluate(
        {"status_code": 200, "body_json": {"best_response": CONSENSUS_ANSWER}},
        "consensus",
    )

    assert ok is True
    assert reasons == []


def test_evaluate_skips_topic_check_for_upload() -> None:
    ok, reasons = live_smart_smoke.evaluate(
        {"status_code": 200, "body_json": {"answer": UPLOAD_ANSWER}},
        "upload",
    )

    assert ok is True
    assert reasons == []


def test_evaluate_rejects_when_answer_field_absent() -> None:
    ok, reasons = live_smart_smoke.evaluate(
        {"status_code": 200, "body_json": {"other_field": SMART_ANSWER}},
        "smart",
    )

    assert ok is False
    assert any("answer field absent" in reason for reason in reasons)


def test_evaluate_rejects_non_200_status() -> None:
    ok, reasons = live_smart_smoke.evaluate(
        {"status_code": 500, "body_json": {"answer": SMART_ANSWER}},
        "smart",
    )

    assert ok is False
    assert any("status_code=500" in reason for reason in reasons)


def test_pattern_defaults_match_matrix() -> None:
    patterns = {"smart", "debate", "consensus", "compare", "upload"}

    assert set(live_smart_smoke.PATTERN_DEFAULT_PROMPT) == patterns
    assert set(live_smart_smoke.PATTERN_EVALUATION) == patterns


def test_argparse_upload_requires_attachment() -> None:
    with pytest.raises(SystemExit) as exc_info:
        live_smart_smoke.parse_args(["--pattern", "upload"])

    assert exc_info.value.code != 0
