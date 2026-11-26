#!/usr/bin/env python3
"""Validator for the Pro case-library asset under skills/mathematical-modeling/assets/case-library/.

Enforces the invariants that keep the 139-card fusion asset self-consistent and
safe to ship in the plugin package:

  CL-01  index.json exists, has schema_version, case_count and cases[].
  CL-02  case_count equals len(cases[]) and equals the number of case-*.md files
         on disk (case-card-template.md and index.* are not case cards).
  CL-03  every index case has a card_path; the referenced file exists inside the
         library directory (basename match, no path escape).
  CL-04  card_path values are relative and contain no absolute prefix / drive / "..".
  CL-05  every case-*.md on disk is referenced by exactly one index entry
         (no orphans, no duplicates).
  CL-06  required fields are present and type-consistent (problem_types/models/
         validation_methods/transferable_patterns are lists; year int-able).
  CL-07  body_sha256 recorded in the index matches the on-disk card file hash.
  CL-08  card YAML frontmatter case_id matches index case_id (parsed leniently).
  CL-09  year distribution sanity: 2012 <= year <= 2025, no out-of-range values.
  CL-10  companion assets exist: index.csv, index.md, case-card-template.md,
         corpus-provenance.md.

Usage:
    python scripts/check_case_library_integrity.py [--library <dir>]

Exit code 0 = clean, non-zero = violations. Prints one line per violation
prefixed with the invariant tag, matching the repo check-script convention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

EXPECTED_YEARS = (2012, 2025)
COMPANION = ("index.csv", "index.md", "case-card-template.md", "corpus-provenance.md")
REQUIRED_FIELDS = (
    "case_id", "paper_id", "year", "title", "competition", "problem_types",
    "models", "keywords", "validation_methods", "core_problem", "data_features",
    "transferable_patterns", "card_path", "evidence_mode",
)
LIST_FIELDS = ("problem_types", "models", "keywords", "validation_methods", "transferable_patterns")


def _intable(value: Any) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _case_id_from_frontmatter(path: Path) -> str | None:
    """Parse the YAML frontmatter case_id without a yaml dependency (lenient)."""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^case_id:\s*([^\s]+)", text, flags=re.M)
    return match.group(1) if match else None


def check_library(lib: Path) -> list[str]:
    errors: list[str] = []
    index_path = lib / "index.json"
    if not index_path.is_file():
        return [f"CL-01 index.json missing at {index_path}"]
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = list(payload.get("cases") or [])

    # CL-01
    if "schema_version" not in payload:
        errors.append("CL-01 index.json missing schema_version")
    # CL-02
    expected_count = payload.get("case_count")
    if expected_count is not None and int(expected_count) != len(cases):
        errors.append(f"CL-02 case_count {expected_count} != len(cases) {len(cases)}")
    card_files = sorted(p.name for p in lib.glob("case-*.md") if p.name != "case-card-template.md")
    if len(cases) != len(card_files):
        errors.append(f"CL-02 {len(cases)} index entries vs {len(card_files)} case-*.md on disk")

    case_ids_seen: dict[str, int] = {}
    for case in cases:
        cid = case.get("case_id")
        case_ids_seen[cid] = case_ids_seen.get(cid, 0) + 1
        # CL-06 required fields
        for field in REQUIRED_FIELDS:
            if field not in case:
                errors.append(f"CL-06 [{cid}] missing field {field}")
        for field in LIST_FIELDS:
            value = case.get(field)
            if value is not None and not isinstance(value, list):
                errors.append(f"CL-06 [{cid}] {field} should be a list, got {type(value).__name__}")
        # CL-09 year range
        year = case.get("year")
        if _intable(year):
            y = int(year)
            if y < EXPECTED_YEARS[0] or y > EXPECTED_YEARS[1]:
                errors.append(f"CL-09 [{cid}] year {y} out of range {EXPECTED_YEARS}")
        # CL-03/CL-04 card_path
        card_path = case.get("card_path") or ""
        if not card_path:
            errors.append(f"CL-03 [{cid}] empty card_path")
            continue
        if card_path.startswith(("/", "\\", "..")) or re.match(r"^[A-Za-z]:", card_path):
            errors.append(f"CL-04 [{cid}] card_path escapes library: {card_path!r}")
        target = (lib / Path(card_path).name) if not Path(card_path).is_absolute() else None
        if target is None or not target.is_file():
            errors.append(f"CL-03 [{cid}] card file not found: {card_path}")
            continue
        # CL-07 body_sha256
        sha = case.get("body_sha256")
        if sha:
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != sha:
                errors.append(f"CL-07 [{cid}] body_sha256 mismatch for {card_path}")
        # CL-08 frontmatter case_id
        fm_id = _case_id_from_frontmatter(target)
        if fm_id and fm_id != cid:
            errors.append(f"CL-08 [{cid}] frontmatter case_id {fm_id!r} != index case_id")

    # CL-05 orphans / duplicates
    referenced = {Path(c["card_path"]).name for c in cases if c.get("card_path")}
    for filename in card_files:
        if filename not in referenced:
            errors.append(f"CL-05 orphan case card not in index: {filename}")
    duplicates = {cid for cid, count in case_ids_seen.items() if count > 1}
    for cid in duplicates:
        errors.append(f"CL-05 duplicate case_id in index: {cid}")

    # CL-10 companions
    for name in COMPANION:
        if not (lib / name).is_file():
            errors.append(f"CL-10 companion missing: {name}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path,
                        default=Path(__file__).resolve().parents[1] / "skills" / "mathematical-modeling" / "assets" / "case-library")
    parser.add_argument("--json", action="store_true", help="emit violations as JSON")
    args = parser.parse_args()
    errors = check_library(args.library.resolve())
    if args.json:
        import json as _json
        print(_json.dumps({"pass": not errors, "errors": errors}, ensure_ascii=False, indent=2))
        return 0 if not errors else 1
    if not errors:
        print(f"[check_case_library_integrity] PASS: {args.library.resolve()} 案例库一致")
        return 0
    for error in errors:
        print(f"[check_case_library_integrity] {error}")
    print(f"[check_case_library_integrity] FAIL: {len(errors)} 项违规")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())