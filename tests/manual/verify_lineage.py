#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_lineage.py — 数据血缘校验器的行为测试（一次性验证，非发布件）。

运行方式：
    python tests/manual/verify_lineage.py
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VALIDATOR = REPO / "scripts" / "validate_data_lineage.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("vl", VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_fixture(root: Path) -> Path:
    (root / "Data" / "raw").mkdir(parents=True)
    (root / "Data" / "processed").mkdir(parents=True)
    (root / "transform").mkdir(parents=True)
    (root / "Data" / "raw" / "source.csv").write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
    (root / "Data" / "processed" / "clean.csv").write_text("a,b,c,ab\n1,2,3,3\n4,5,6,20\n", encoding="utf-8")
    (root / "transform" / "clean.txt").write_text("op: add_column ab = a*b\n", encoding="utf-8")
    return root


def make_ledger(root: Path, vl) -> dict:
    raw = vl._sha256(root / "Data" / "raw" / "source.csv")
    out = vl._sha256(root / "Data" / "processed" / "clean.csv")
    scr = vl._sha256(root / "transform" / "clean.txt")
    return {
        "schema_version": "data-lineage/1.0",
        "project_id": "verify",
        "generated_at": "2026-11-26",
        "raw": {"files": [{"path": "Data/raw/source.csv", "sha256": raw, "rows": 2, "cols": 3,
                           "data_class": "contest_provided"}]},
        "stages": [{
            "stage": "processed",
            "inputs": [{"path": "Data/raw/source.csv", "sha256": raw, "source_stage": "raw"}],
            "transform": {"script": "transform/clean.txt", "script_sha256": scr,
                          "params": {"add": "ab=a*b"}, "random_seed": 0,
                          "operations": [{"op": "add_column", "columns": ["ab"], "reason": "a*b"}]},
            "outputs": [{"path": "Data/processed/clean.csv", "sha256": out, "rows": 2, "cols": 4}],
            "diff": {"rows_delta": 0, "cols_delta": 1},
        }],
        "invariants": {"raw_unmodified": True, "chain_continuous": True, "reproducible": True},
    }


def run(vl, ledger: dict, root: Path) -> dict:
    f = vl.Findings()
    vl.verify_raw(ledger, root, f)
    vl.verify_stages(ledger, root, f)
    vl.verify_invariants(ledger, f)
    return f.result()


def main() -> int:
    vl = load_validator()
    failures = []

    # 1) 正常用例应 PASS
    with tempfile.TemporaryDirectory() as td:
        root = build_fixture(Path(td))
        ledger = make_ledger(root, vl)
        r = run(vl, ledger, root)
        print(f"[1] valid lineage        -> {r['status']} (expect PASS)")
        if r["status"] != "PASS":
            failures.append(("valid", r["errors"]))

    # 2) raw 被篡改应 FAIL
    with tempfile.TemporaryDirectory() as td:
        root = build_fixture(Path(td))
        ledger = make_ledger(root, vl)
        (root / "Data" / "raw" / "source.csv").write_text("a,b,c\n9,9,9\n", encoding="utf-8")
        r = run(vl, ledger, root)
        print(f"[2] raw tampered         -> {r['status']} (expect FAIL)")
        if r["status"] != "FAIL":
            failures.append(("raw_tamper", r))
        elif not any("哈希不符" in e for e in r["errors"]):
            failures.append(("raw_tamper_msg", r["errors"]))

    # 3) 产物被改应 FAIL
    with tempfile.TemporaryDirectory() as td:
        root = build_fixture(Path(td))
        ledger = make_ledger(root, vl)
        (root / "Data" / "processed" / "clean.csv").write_text("a,b,c,ab\n1,2,3,99\n", encoding="utf-8")
        r = run(vl, ledger, root)
        print(f"[3] output tampered      -> {r['status']} (expect FAIL)")
        if r["status"] != "FAIL":
            failures.append(("output_tamper", r))

    # 4) 血缘断链应 FAIL（输入不在上一级产物里）
    with tempfile.TemporaryDirectory() as td:
        root = build_fixture(Path(td))
        ledger = make_ledger(root, vl)
        ledger["stages"][0]["inputs"][0]["path"] = "Data/raw/other.csv"
        r = run(vl, ledger, root)
        print(f"[4] broken chain         -> {r['status']} (expect FAIL)")
        if r["status"] != "FAIL":
            failures.append(("broken_chain", r))
        elif not any("血缘断裂" in e for e in r["errors"]):
            failures.append(("broken_chain_msg", r["errors"]))

    # 5) 缺变换脚本记录应 FAIL
    with tempfile.TemporaryDirectory() as td:
        root = build_fixture(Path(td))
        ledger = make_ledger(root, vl)
        ledger["stages"][0]["transform"] = {}
        r = run(vl, ledger, root)
        print(f"[5] no transform record  -> {r['status']} (expect FAIL)")
        if r["status"] != "FAIL":
            failures.append(("no_transform", r))

    # 6) 阶段顺序错应 FAIL
    with tempfile.TemporaryDirectory() as td:
        root = build_fixture(Path(td))
        ledger = make_ledger(root, vl)
        st = ledger["stages"][0]
        ledger["stages"] = [
            dict(st, stage="feature"),
            dict(st, stage="processed"),
        ]
        r = run(vl, ledger, root)
        has_order_fail = any("顺序错误" in e for e in r["errors"])
        print(f"[6] wrong stage order    -> {'FAIL(order)' if has_order_fail else 'no order error'} (expect order error)")
        if not has_order_fail:
            failures.append(("stage_order", r))

    print()
    if failures:
        print(f"FAILED {len(failures)} case(s):")
        for name, detail in failures:
            print(f"  - {name}: {detail}")
        return 1
    print("ALL 6 CASES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
