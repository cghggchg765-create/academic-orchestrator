import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "skills" / "humanizer" / "src"))
from providers.agent_lm_quality import ProtectedText, evaluate_rewrite, protect_tokens


def test_protection_preserves_full_tokens_and_order():
    text = r"提升 12.3%（p<0.01，N=500），公式 $x_i\leq 1$，见[Smith2024]。"
    protected = protect_tokens(text)
    assert protected.tokens == ("12.3%", "p<0.01", "N=500", r"$x_i\leq 1$", "[Smith2024]")
    assert protected.restore(protected.masked) == text
    assert evaluate_rewrite(text, text)["status"] == "PASS"


def test_protection_rejects_missing_and_duplicate_tokens():
    text = "结果为 95%，见[Smith2024]。"
    assert evaluate_rewrite(text, "结果为 90%，见[Smith2024]。")["status"] == "FAIL"
    assert evaluate_rewrite(text, "结果为 95%，见[Smith2024]。[Smith2024]")["status"] == "FAIL"


def test_restore_rejects_placeholder_corruption():
    protected = protect_tokens("结果为 95%。")
    try:
        protected.restore("结果为 __MM_PROTECTED_0__ __MM_PROTECTED_0__。")
    except ValueError:
        pass
    else:
        raise AssertionError("placeholder duplication must be rejected")


def test_evaluate_rewrite_accepts_masked_candidate_and_restored_candidate():
    original = "结果为 95%，见[Smith2024]。"
    protected = protect_tokens(original)
    masked = "结果为 __MM_PROTECTED_0__，见__MM_PROTECTED_1__。"
    assert evaluate_rewrite(original, masked)["status"] == "PASS"
    assert evaluate_rewrite(original, protected.restore(masked))["status"] == "PASS"


def test_evaluate_rewrite_fails_closed_for_missing_or_duplicate_placeholder():
    original = "结果为 95%，见[Smith2024]。"
    assert evaluate_rewrite(
        original, "结果为 __MM_PROTECTED_0__，见。"
    )["status"] == "FAIL"
    duplicate = "结果为 __MM_PROTECTED_0__，见__MM_PROTECTED_0__。"
    result = evaluate_rewrite(original, duplicate)
    assert result["status"] == "FAIL"
    assert "PROTECTED_PLACEHOLDER_INVALID" in result["failure_reasons"]


def test_overlapping_ai_patterns_are_not_double_counted():
    from humanizer_tools import detect_ai_patterns

    delve = detect_ai_patterns("We delve deeper into the result.")
    assert [item["pattern"] for item in delve] == ["delve_deeper"]
    leverage = detect_ai_patterns("We leverage the method.")
    assert [item["pattern"] for item in leverage] == ["leverage_utilize_repeat"]


def test_ai_score_does_not_short_circuit_on_cjk_text():
    from humanizer_tools import compute_ai_score, detect_ai_patterns

    # CJK has no whitespace separators; before the fix ``text.split()`` counted
    # this whole sentence as one word and scoring always returned 0.0.
    mixed = "It's worth noting，本文首先对数据进行深入分析，模型具有重要的科学意义，结果达到预期的精度要求。"
    detections = detect_ai_patterns(mixed)
    assert [item["pattern"] for item in detections] == ["formulaic_opener"]
    assert compute_ai_score(mixed, detections) > 0.0


def test_ai_score_zero_for_clean_cjk_text():
    from humanizer_tools import compute_ai_score, detect_ai_patterns

    zh = "本文首先对数据进行深入分析，模型具有重要的科学意义，结果达到预期的精度要求。" * 3
    assert compute_ai_score(zh, detect_ai_patterns(zh)) == 0.0


def test_post_process_skip_reason_is_not_inverted():
    from humanizer_tools import post_process_skip_reason

    assert post_process_skip_reason([], 0.0) == "no patterns found"
    assert "score too low" in post_process_skip_reason([{"pattern": "em_dash_overuse"}], 0.1)
