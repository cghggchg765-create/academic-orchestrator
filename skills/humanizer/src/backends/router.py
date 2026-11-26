"""Route diagnosis and rewrite requests to the host Agent LM sub-agent.

This module deliberately does not rewrite text. The host plugin executes the
returned request with the language/domain-specific sub-agent, then submits the
candidate to the deterministic evaluator.
"""
from __future__ import annotations

from .chinese import ChineseAcademicHumanizer
from .language_detect import detect_language


def build_subagent_request(text: str, *, language: str | None = None,
                           domain: str = "academic") -> dict:
    lang = language or detect_language(text)
    if lang == "zh":
        backend = ChineseAcademicHumanizer()
    else:
        raise ValueError(
            "English routing remains owned by the existing academic-humanize; "
            "this adapter only exposes the host-agent contract for Chinese text."
        )
    findings = backend.diagnose(text)
    request = backend.build_rewrite_request(text, findings)
    request.update({
        "executor": "host_plugin_subagent",
        "rewrite_authority": "corresponding_language_domain_subagent",
        "domain": domain,
        "candidate_required": True,
        "local_rewrite_permitted": False,
        "evaluation_required_after_rewrite": True,
    })
    return request
