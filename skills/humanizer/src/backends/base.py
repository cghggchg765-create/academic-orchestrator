"""Language-specific humanizer backend contracts."""
from __future__ import annotations

from typing import Protocol


class AcademicHumanizerBackend(Protocol):
    language: str

    def diagnose(self, text: str) -> list[dict]: ...

    def build_rewrite_request(self, text: str, findings: list[dict]) -> dict: ...

    def evaluate(self, original: str, rewritten: str) -> dict: ...
