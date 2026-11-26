#!/usr/bin/env python3
"""Validate a math-modeling figure/result/claim trace deterministically."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(payload: dict, root: Path) -> list[str]:
    errors: list[str] = []
    for trace in payload.get("traces", []):
        for source in trace.get("source_data", []):
            if not (root / source["path"]).exists():
                errors.append(f"{trace['trace_id']}: missing source {source['path']}")
        output = trace.get("output", {})
        output_path = root / output.get("path", "")
        if not output_path.exists():
            errors.append(f"{trace['trace_id']}: missing output {output.get('path')}")
        elif output.get("hash") and output["hash"] != _hash(output_path):
            errors.append(f"{trace['trace_id']}: output hash mismatch")
        transformation = trace.get("transformation", {})
        script_path = root / transformation.get("script", "")
        if not script_path.exists():
            errors.append(f"{trace['trace_id']}: missing transformation {transformation.get('script')}")
        elif transformation.get("script_hash") and transformation["script_hash"] != _hash(script_path):
            errors.append(f"{trace['trace_id']}: transformation hash mismatch")
        if not trace.get("manuscript_claim", {}).get("locator"):
            errors.append(f"{trace['trace_id']}: manuscript claim locator missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    payload = json.loads(args.trace.read_text(encoding="utf-8"))
    errors = validate(payload, args.root)
    report = {"status": "PASS" if not errors else "FAIL", "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
