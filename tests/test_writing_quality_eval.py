"""Regression tests for the offline writing-quality eval gate (run_writing_quality)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
EVAL_SCRIPT = ROOT / "scripts" / "evals" / "run_writing_quality.py"

spec = importlib.util.spec_from_file_location("run_writing_quality", EVAL_SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_expected_fail_keeps_diagnostics_and_skips_review():
    item = {
        "id": "t1",
        "text": "结果为 95%，见[Smith2024]。",
        "candidate": "结果为 96%，见[Smith2024]。",
        "protected": ["95%"],
        "expected_verdict": "FAIL",
    }
    result = module._result(item)
    assert result["status"] == "PASS"  # the guard rejected as the fixture expects
    assert "PROTECTED_TOKEN_MISSING" in result["failure_reasons"]  # diagnostics preserved
    assert result["review_required"] is False  # fixture pre-commits the review


def test_expected_fail_not_triggered_is_reported():
    item = {"id": "t2", "text": "结果为 95%。", "candidate": "结果为 95%。", "expected_verdict": "FAIL"}
    result = module._result(item)
    assert result["status"] == "FAIL"
    assert "EXPECTED_FAIL_NOT_TRIGGERED" in result["failure_reasons"]


def test_declared_claim_change_is_flagged():
    item = {
        "id": "t3",
        "text": "平均误差为4.2%。",
        "candidate": "平均误差为4.5%。",
        "claims": ["mean_error=4.2%"],
        "expected_verdict": "FAIL",
    }
    result = module._result(item)
    assert result["status"] == "PASS"
    assert any(reason.startswith("CLAIM_CHANGED") for reason in result["failure_reasons"])
    assert result["checks"]["claim_fidelity"] is False


def test_claim_not_in_original_marks_fixture_malformed():
    item = {"id": "t4", "text": "平均误差为4.2%。", "claims": ["mean_error=9.9%"]}
    result = module._result(item)
    assert any(reason.startswith("CLAIM_NOT_IN_ORIGINAL") for reason in result["failure_reasons"])