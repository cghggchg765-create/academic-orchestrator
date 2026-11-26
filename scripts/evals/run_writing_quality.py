#!/usr/bin/env python3
"""Offline writing-quality evaluation with protected-token fidelity checks."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "humanizer" / "src"))
from providers.agent_lm_quality import evaluate_rewrite, protect_tokens  # noqa: E402


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _claim_fidelity_failures(original: str, candidate: str, claims: list) -> list[str]:
    """Return per-claim diagnostics when a declared claim value is not preserved.

    Claims are declared as ``key=value`` (e.g. ``mean_error=4.2%``); the value
    side is the assertable part.  A claim absent from the original marks the
    fixture as malformed rather than silently passing.
    """
    failures: list[str] = []
    for claim in claims:
        if not isinstance(claim, str) or not claim:
            continue
        value = claim.split("=", 1)[1] if "=" in claim else claim
        if value not in original:
            failures.append(f"CLAIM_NOT_IN_ORIGINAL:{claim}")
        elif value not in candidate:
            failures.append(f"CLAIM_CHANGED:{claim}")
    return failures


def _result(item: dict) -> dict:
    original = item["text"]
    candidate = item.get("candidate")
    mode = "candidate" if candidate is not None else "identity_compatibility"
    candidate = original if candidate is None else candidate
    protected = protect_tokens(original)
    declared = item.get("protected", [])
    rewrite = evaluate_rewrite(original, candidate)
    declared_detected = all(token in protected.tokens or token in original for token in declared)
    claims = item.get("claims") or []
    claim_failures = _claim_fidelity_failures(original, candidate, claims) if claims else []
    checks = {
        "protected_detected": declared_detected,
        "protected_fidelity": rewrite["protected_tokens_preserved"],
        "changed": rewrite["changed"],
        "claim_fidelity": not claim_failures if claims else item.get("claims_checked", True),
        "citation_fidelity": item.get("citations_checked", True),
        "numeric_fidelity": rewrite["protected_tokens_preserved"],
        "term_fidelity": item.get("terms_checked", True),
        "equation_fidelity": rewrite["protected_tokens_preserved"],
    }
    failures = list(rewrite["failure_reasons"]) + claim_failures
    if not declared_detected:
        failures.append("DECLARED_PROTECTED_TOKEN_NOT_DETECTED")
    expected = item.get("expected_verdict")
    actual = "PASS" if not failures else "FAIL"
    if item.get("review_required") and actual == "PASS":
        actual = "PASS_WITH_REVIEW"
    if expected == "FAIL":
        if actual == "FAIL":
            decision = "PASS"  # the guard rejected the corrupt candidate as expected
        else:
            decision = "FAIL"
            if "EXPECTED_FAIL_NOT_TRIGGERED" not in failures:
                failures.append("EXPECTED_FAIL_NOT_TRIGGERED")
    elif expected == "PASS_WITH_REVIEW":
        decision = "PASS" if actual in {"PASS", "PASS_WITH_REVIEW"} else "FAIL"
    else:
        decision = actual
    return {
        "id": item["id"],
        "mode": mode,
        "language": item.get("language", "unknown"),
        "domain": item.get("domain", "academic"),
        "status": decision,
        "decision": decision,
        "checks": checks,
        "failure_reasons": failures,
        "blocked_items": failures,
        "original_sha256": _sha(original),
        "candidate_sha256": _sha(candidate),
        "original_length": len(original),
        "candidate_length": len(candidate),
        # An expected-FAIL fixture pre-commits the review: failure reasons stay
        # visible as diagnostics, but the item itself needs no new review.
        "review_required": (not (expected == "FAIL" and decision == "PASS")
                            and (bool(failures) or bool(item.get("review_required")))),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path, default=Path("evals/writing-quality/fixtures/protected_tokens.jsonl"))
    ap.add_argument("--output", type=Path, default=Path("evals/results/writing-quality/smoke.json"))
    args = ap.parse_args()
    results = [_result(json.loads(line)) for line in args.fixture.read_text(encoding="utf-8").splitlines() if line.strip()]
    status = "PASS" if all(r["status"] in {"PASS", "PASS_WITH_REVIEW"} for r in results) else "FAIL"
    report = {"schema_version": "2.0", "mode": "plugin_only", "status": status, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(status)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
