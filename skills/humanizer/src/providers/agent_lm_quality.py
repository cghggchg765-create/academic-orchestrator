"""Deterministic contracts for protected academic-text rewrites."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_PLACEHOLDER = re.compile(r"__MM_PROTECTED_(\d+)__")


@dataclass(frozen=True)
class ProtectedText:
    masked: str
    tokens: tuple[str, ...]

    def restore(self, text: str) -> str:
        found = [int(m.group(1)) for m in _PLACEHOLDER.finditer(text)]
        expected = list(range(len(self.tokens)))
        if sorted(found) != expected:
            raise ValueError("protected placeholders are missing, duplicated, or out of range")
        for i, token in enumerate(self.tokens):
            text = text.replace(f"__MM_PROTECTED_{i}__", token)
        return text


def protect_tokens(text: str) -> ProtectedText:
    patterns = [
        r"```[\s\S]*?```",
        r"\\\([^\n]*?\\\)", r"\\\[[\s\S]*?\\\]",
        r"\$\$[\s\S]*?\$\$", r"\$[^$\n]+\$",
        r"\[[^\]\n]+\]",
        r"\b(?:p\s*[<=>]\s*0?\.\d+|N\s*=\s*\d+)\b",
        r"(?<![0-9A-Za-z_.])\d+(?:\.\d+)?%",
        r"(?<![0-9A-Za-z_.])\d+(?:\.\d+)?(?![0-9A-Za-z_.])",
    ]
    tokens: list[str] = []
    combined = re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)

    def repl(match: re.Match[str]) -> str:
        tokens.append(match.group(0))
        return f"__MM_PROTECTED_{len(tokens)-1}__"

    return ProtectedText(combined.sub(repl, text), tuple(tokens))


def _token_check(original: str, rewritten: str) -> dict:
    protected = protect_tokens(original).tokens
    observed = protect_tokens(rewritten).tokens
    missing = [token for token in protected if token not in rewritten]
    counts_original = {token: protected.count(token) for token in set(protected)}
    counts_rewritten = {token: observed.count(token) for token in set(observed)}
    duplicated = [token for token, count in counts_rewritten.items()
                  if token in counts_original and count > counts_original[token]]
    filtered_observed = tuple(token for token in observed if token in counts_original)
    preserved = not missing and not duplicated and protected == filtered_observed
    return {
        "protected_tokens_preserved": preserved,
        "missing_tokens": missing,
        "duplicated_tokens": duplicated,
        "original_tokens": list(protected),
        "rewritten_tokens": list(observed),
    }


def protected_tokens_preserved(original: str, rewritten: str) -> bool:
    return _token_check(original, rewritten)["protected_tokens_preserved"]


def build_rewrite_request(text: str, findings: list[dict]) -> dict:
    protected = protect_tokens(text)
    return {
        "provider": "agent_lm",
        "mode": "plugin_only",
        "instruction": "Improve natural academic expression without changing claims, evidence, numbers, formulas, code, citations, or terminology.",
        "findings": findings,
        "masked_text": protected.masked,
        "protected_count": len(protected.tokens),
        "original_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "constraints": [
            "Return only the rewritten text.",
            "Do not invent data, citations, results, or links.",
            "Preserve every protected token exactly after restoration.",
            "If a claim is unsupported, flag it instead of adding evidence.",
        ],
    }


def evaluate_rewrite(original: str, rewritten: str) -> dict:
    """Evaluate either a restored candidate or the masked candidate directly.

    ``build_rewrite_request`` asks providers to return masked text.  When
    placeholders are present, validate their complete sequence and restore
    before checking tokens.  Malformed placeholders fail closed rather than
    being treated as ordinary candidate text.
    """
    failures: list[str] = []
    candidate = rewritten
    if _PLACEHOLDER.search(rewritten):
        protected = protect_tokens(original)
        found = [int(m.group(1)) for m in _PLACEHOLDER.finditer(rewritten)]
        expected = list(range(len(protected.tokens)))
        if sorted(found) != expected:
            failures.append("PROTECTED_PLACEHOLDER_INVALID")
        else:
            candidate = protected.restore(rewritten)

    token_check = _token_check(original, candidate) if not failures else _token_check(original, original)
    if token_check["missing_tokens"]:
        failures.append("PROTECTED_TOKEN_MISSING")
    if token_check["duplicated_tokens"]:
        failures.append("PROTECTED_TOKEN_DUPLICATED")
    if not token_check["protected_tokens_preserved"]:
        failures.append("PROTECTED_TOKEN_ORDER_OR_CONTENT_CHANGED")
    return {
        "status": "PASS" if not failures else "FAIL",
        **token_check,
        "changed": original != candidate,
        "failure_reasons": failures,
        "original_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "rewritten_sha256": hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
        "original_length": len(original),
        "rewritten_length": len(candidate),
        "review_required": bool(failures),
    }
