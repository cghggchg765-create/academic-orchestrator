import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "skills" / "humanizer" / "src"))
from backends.chinese import ChineseAcademicHumanizer
from backends.language_detect import detect_language
from backends.router import build_subagent_request


def test_detects_chinese_and_diagnoses_templates():
    text = "本文首先进行深入分析，最后证明了模型具有重要意义。"
    assert detect_language(text) == "zh"
    findings = ChineseAcademicHumanizer().diagnose(text)
    assert {item["category"] for item in findings} >= {"C1", "C2", "C4", "C5"}


def test_request_explicitly_delegates_rewrite_to_host_subagent():
    text = "本文首先分析数据，结果为95%，见[Smith2024]。"
    request = build_subagent_request(text, domain="mathematical_modeling")
    assert request["executor"] == "host_plugin_subagent"
    assert request["local_rewrite_permitted"] is False
    assert request["candidate_required"] is True
    assert "95%" in request["masked_text"] or "__MM_PROTECTED_" in request["masked_text"]
