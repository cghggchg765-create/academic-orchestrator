#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据血缘校验器（D1 门禁的机器执行者）。

回答三个问题并给出可核对结论：
  1. 处理了什么   → raw.files 的 path/rows/cols/sha256 是否与磁盘一致
  2. 怎么处理     → 每个 stage 的 transform.script 是否存在、哈希是否匹配
  3. 产出什么     → outputs 的 sha256/rows/cols 是否与磁盘一致
  并校验链式连续性：下一级 inputs 必须匹配上一级 outputs 的 path+sha256。

用法:
  python scripts/validate_data_lineage.py Data/data-lineage.json --root .
  python scripts/validate_data_lineage.py Data/data-lineage.json --root . --json
  python scripts/validate_data_lineage.py Data/data-lineage.json --root . --require-schema
  python scripts/validate_data_lineage.py --check-raw    # 只查 raw 是否被改动

退出码：0 = 全部通过；1 = 有 FAIL；2 = 文件/schema 问题
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# 必填字段（P1-13）：以 schema 的 required 为唯一事实源，不在校验器里维护副本。
# 找不到 schema 时才退回这里的兜底集合（与 schema 保持一致）。
REQUIRED_TOP_FALLBACK = ("schema_version", "project_id", "generated_at",
                         "raw", "stages", "invariants")


def _required_top(root: Path) -> tuple:
    """从 data_lineage.schema.json 的 required 读取必填字段。"""
    for cand in (
        Path(__file__).resolve().parent.parent / "shared" / "contracts" / "math_modeling" / "data_lineage.schema.json",
        root / "shared" / "contracts" / "math_modeling" / "data_lineage.schema.json",
    ):
        if cand.is_file():
            try:
                req = json.loads(cand.read_text(encoding="utf-8")).get("required")
                if isinstance(req, list) and req:
                    return tuple(req)
            except (OSError, json.JSONDecodeError):
                pass
    return REQUIRED_TOP_FALLBACK
STAGE_ORDER = ["processed", "feature", "test_result"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_columns(path: Path) -> int | None:
    """仅对 csv/tsv 做列数快查（不引依赖）。其它格式返回 None。"""
    if path.suffix.lower() not in (".csv", ".tsv"):
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            header = fh.readline()
        if not header.strip():
            return 0
        sep = "\t" if path.suffix.lower() == ".tsv" else ","
        return len(header.rstrip("\n").split(sep))
    except OSError:
        return None


class Findings:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks: list[dict] = []

    def check(self, cid: str, ok: bool, detail: str, severity: str = "FAIL",
              ok_detail: str | None = None):
        """登记一条判定。detail 描述"不通过时"的具体原因；ok_detail 描述通过时的状态，
        避免通过项也打印失败文案（否则报告自相矛盾）。"""
        status = "PASS" if ok else severity
        shown = (ok_detail or "通过") if ok else detail
        self.checks.append({"id": cid, "status": status, "detail": shown,
                            "failure_detail": None if ok else detail})
        if not ok:
            (self.errors if severity == "FAIL" else self.warnings).append(f"[{cid}] {detail}")

    def result(self) -> dict:
        ok = not self.errors
        return {
            "status": "PASS" if ok else "FAIL",
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _count_rows(path: Path) -> int | None:
    """CSV/TSV 数据行数（不含表头）。其它格式返回 None。"""
    if path.suffix.lower() not in (".csv", ".tsv"):
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            n = sum(1 for line in fh if line.strip())
        return max(n - 1, 0)
    except OSError:
        return None


def verify_environment_lock(payload: dict, root: Path, f: Findings) -> None:
    """环境锁定校验（可复现性最小成本方案）。

    NeurIPS 等可复现性清单要求披露运行环境；这里不做容器化，只要求：
    有 lock 文件 + 哈希匹配。缺失记 WARN（不阻断，但审计可见）。
    """
    env = payload.get("environment_lock")
    if not isinstance(env, dict) or not env.get("file"):
        f.check("env_lock.present", False,
                "未记录 environment_lock（建议 pip freeze > Code/requirements.lock 后登记其哈希）",
                severity="WARN", ok_detail="环境锁定已登记")
        return
    rel = env["file"]
    full = root / rel
    if not full.exists():
        f.check("env_lock.exists", False, f"环境锁文件不存在: {rel}")
        return
    actual = _sha256(full)
    declared = (env.get("sha256") or "").lower()
    f.check("env_lock.sha256", actual == declared,
            f"环境锁 {rel} 哈希不符：登记 {declared[:12]}… 实际 {actual[:12]}…（依赖已变）",
            ok_detail=f"环境锁 {rel} 与登记一致")


def _norm_path(p: str) -> str:
    """路径归一化（P1-16）：统一分隔符 + 小写。

    Windows 上 `Data\\raw\\a.csv` 与 `Data/raw/a.csv` 是同一文件，但字典键精确匹配
    会判成"血缘断裂"。统一 as_posix + casefold（Windows 文件系统大小写不敏感）。
    """
    s = str(p).replace("\\", "/").strip()
    while "//" in s:
        s = s.replace("//", "/")
    return s.casefold()


def verify_raw(payload: dict, root: Path, f: Findings) -> None:
    """raw 只读性：磁盘哈希必须等于登记哈希；登记的行列数需与实际一致。"""
    files = (payload.get("raw") or {}).get("files") or []
    if not files:
        f.check("raw.present", False, "raw.files 为空：无法证明原始数据未被篡改")
        return
    for item in files:
        rel = item.get("path", "")
        full = root / rel
        if not full.exists():
            f.check(f"raw.exists:{rel}", False, f"原始数据缺失: {rel}")
            continue
        actual = _sha256(full)
        declared = (item.get("sha256") or "").lower()
        f.check(f"raw.sha256:{rel}", actual == declared,
                f"{rel} 哈希不符：登记 {declared[:12]}… 实际 {actual[:12]}…（原始数据被修改）",
                ok_detail=f"{rel} 哈希与登记一致，原始数据未被篡改")
        cols = _count_columns(full)
        declared_cols = item.get("cols")
        if cols is not None and isinstance(declared_cols, int) and cols != declared_cols:
            f.check(f"raw.cols:{rel}", False,
                    f"{rel} 列数不符：登记 {declared_cols} 实际 {cols}", severity="WARN")
        rows = _count_rows(full)
        declared_rows = item.get("rows")
        if rows is not None and isinstance(declared_rows, int) and rows != declared_rows:
            f.check(f"raw.rows:{rel}", False,
                    f"{rel} 行数不符：登记 {declared_rows} 实际 {rows}（登记与实际数据不一致）",
                    ok_detail=f"{rel} 行数与登记一致")


def verify_stages(payload: dict, root: Path, f: Findings) -> None:
    stages = payload.get("stages") or []
    if not stages:
        f.check("stages.present", False, "stages 为空：没有记录任何处理过程")
        return
    names = [s.get("stage") for s in stages]
    # 阶段顺序必须单调（允许跳过，不允许回退）
    idx = [STAGE_ORDER.index(n) for n in names if n in STAGE_ORDER]
    f.check("stages.order", idx == sorted(idx),
            f"处理阶段顺序错误: {names}（应为 {STAGE_ORDER} 的子序列且递增）",
            ok_detail=f"处理阶段顺序正确: {names}")

    # 链式连续性：prev_outputs 的 {path, sha256} 必须覆盖本 stage 的每个 input。
    # 键统一走 _norm_path（P1-16），避免 `Data\raw\a.csv` 与 `Data/raw/a.csv` 被当成两个文件。
    prev_outputs: dict[str, str] = {}
    for item in (payload.get("raw") or {}).get("files") or []:
        prev_outputs[_norm_path(item.get("path", ""))] = (item.get("sha256") or "").lower()
    prev_label = "raw"

    for st in stages:
        name = st.get("stage", "?")
        # 输入必须来自上一级
        for inp in st.get("inputs") or []:
            p = inp.get("path", "")
            key = _norm_path(p)
            want = (inp.get("sha256") or "").lower()
            if key not in prev_outputs:
                f.check(f"chain.{name}.input:{p}", False,
                        f"{name} 的输入 {p} 不在上一级({prev_label})产物中——数据血缘断裂")
                continue
            got = prev_outputs[key]
            f.check(f"chain.{name}.input_sha:{p}", got == want,
                    f"{name} 输入 {p} 哈希与上一级不符：上级 {got[:12]}… 本级声明 {want[:12]}…",
                    ok_detail=f"{name} 输入 {p} 与上级 {prev_label} 哈希一致")

        # 变换脚本存在且哈希匹配
        tr = st.get("transform") or {}
        script_rel = tr.get("script", "")
        if not script_rel:
            f.check(f"transform.script:{name}", False, f"{name} 未记录变换脚本——过程不可复现")
        else:
            sp = root / script_rel
            if not sp.exists():
                f.check(f"transform.exists:{name}", False, f"{name} 变换脚本缺失: {script_rel}")
            else:
                actual = _sha256(sp)
                declared = (tr.get("script_sha256") or "").lower()
                f.check(f"transform.sha:{name}", actual == declared,
                        f"{name} 变换脚本哈希不符：登记 {declared[:12]}… 实际 {actual[:12]}…",
                        ok_detail=f"{name} 变换脚本哈希匹配，过程可复现")
        if not tr.get("random_seed") and tr.get("random_seed") != 0:
            f.check(f"transform.seed:{name}", False,
                    f"{name} 未记录随机种子（若该阶段不涉及随机性可填 0）", severity="WARN")
        # 参数记录：无 params 说明"怎么处理"不可复核
        if not isinstance(tr.get("params"), dict) or not tr.get("params"):
            f.check(f"transform.params:{name}", False,
                    f"{name} 未记录处理参数（params 为空）——处理过程无法复核", severity="WARN")
        # 逐条操作记录：行数变化必须能被 operations 解释
        ops = tr.get("operations")
        if not isinstance(ops, list) or not ops:
            f.check(f"transform.operations:{name}", False,
                    f"{name} 未记录逐条处理动作（operations 为空）——无法核对做了什么",
                    severity="WARN")
        else:
            bad = [i for i, o in enumerate(ops)
                   if not isinstance(o, dict) or not o.get("op")]
            f.check(f"transform.operations_shape:{name}", not bad,
                    f"{name} operations 第 {bad[:5]} 项缺少 op 字段")

        # 产物存在且哈希匹配；行列数需与登记一致
        outs: dict[str, str] = {}
        # P1-15：prev_rows 必须按本 stage 的某个具体 input 精确定位，
        # 不能取"上一 stage 最后一个 output"（多 output 时基准错位，
        # 会让合法台账被误判 FAIL）。建立 path → rows 索引后按 input 查。
        prev_rows_by_path: dict[str, int] = {}
        for item in (payload.get("raw") or {}).get("files") or []:
            if isinstance(item.get("rows"), int):
                prev_rows_by_path[_norm_path(item.get("path", ""))] = item["rows"]
        for st_prev in stages[:stages.index(st)]:
            for o in st_prev.get("outputs") or []:
                if isinstance(o.get("rows"), int):
                    prev_rows_by_path[_norm_path(o.get("path", ""))] = o["rows"]
        # 本 stage 各 input 的 rows（取有 rows 的第一个作为 diff 基准）
        prev_rows = None
        for inp in st.get("inputs") or []:
            r = prev_rows_by_path.get(_norm_path(inp.get("path", "")))
            if isinstance(r, int):
                prev_rows = r
                break
        if prev_rows is None and len(prev_rows_by_path) == 1:
            # 只有一个上游产物时，它是唯一合理基准
            prev_rows = next(iter(prev_rows_by_path.values()))
        for out in st.get("outputs") or []:
            rel = out.get("path", "")
            full = root / rel
            if not full.exists():
                f.check(f"output.exists:{name}:{rel}", False, f"{name} 产物缺失: {rel}")
                continue
            actual = _sha256(full)
            declared = (out.get("sha256") or "").lower()
            f.check(f"output.sha:{name}:{rel}", actual == declared,
                    f"{name} 产物 {rel} 哈希不符：登记 {declared[:12]}… 实际 {actual[:12]}…",
                    ok_detail=f"{name} 产物 {rel} 哈希与登记一致")
            outs[_norm_path(rel)] = actual
            # 行/列数与磁盘一致性
            rows = _count_rows(full)
            if rows is not None and isinstance(out.get("rows"), int) and rows != out["rows"]:
                f.check(f"output.rows:{name}:{rel}", False,
                        f"{name} 产物 {rel} 行数不符：登记 {out['rows']} 实际 {rows}")
            cols = _count_columns(full)
            if cols is not None and isinstance(out.get("cols"), int) and cols != out["cols"]:
                f.check(f"output.cols:{name}:{rel}", False,
                        f"{name} 产物 {rel} 列数不符：登记 {out['cols']} 实际 {cols}")
            # diff 与实际行数变化一致
            diff = st.get("diff") or {}
            if isinstance(diff.get("rows_delta"), int) and isinstance(out.get("rows"), int) \
                    and isinstance(prev_rows, int):
                expect = out["rows"] - prev_rows
                f.check(f"diff.rows_delta:{name}", diff["rows_delta"] == expect,
                        f"{name} diff.rows_delta={diff['rows_delta']} 与实测变化 {expect}"
                        f"（{prev_rows}→{out['rows']}）不一致")
        if not outs:
            f.check(f"output.present:{name}", False, f"{name} 没有任何产物")
            continue
        prev_outputs, prev_label = outs, name


def verify_raw_lock(payload: dict, root: Path, f: Findings) -> None:
    """独立 raw 锁定基线校验（若存在 Data/raw_lock.json 则以它为准）。

    这解决了"raw 哈希由 dataprep 自己登记 → 先改后登记"的漏洞：
    raw_lock 由主 Agent 在 N0/N1（处理前）建立，dataprep 无权改写。

    P1-17：raw.files 非空却没有锁定基线时判 FAIL——否则"原始数据只读"
    只在建立 lock 之后才成立，D1 可以完全不依赖 lock 而通过。
    raw.files 为空时维持原有的 WARN 判定（无原始数据可锁）。
    """
    lock_path = root / "Data" / "raw_lock.json"
    raw_files = (payload.get("raw") or {}).get("files") or []
    if not lock_path.exists():
        if raw_files:
            f.check("raw_lock.present", False,
                    "未建立原始数据锁定基线 Data/raw_lock.json（无法证明处理前 raw 未被改动）："
                    "raw.files 非空时必须先用 python scripts/raw_lock.py --root <项目> "
                    "建立处理前基线",
                    ok_detail="raw 锁定基线存在")
        else:
            f.check("raw_lock.present", False,
                    "未建立原始数据锁定基线 Data/raw_lock.json（无法证明处理前 raw 未被改动）",
                    severity="WARN",
                    ok_detail="raw 锁定基线存在")
        return
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        f.check("raw_lock.parse", False, f"raw_lock.json 无法解析: {exc}")
        return
    base = lock.get("files") or {}
    if not base:
        f.check("raw_lock.files", False, "raw_lock.json 中 files 为空")
        return
    for rel, meta in base.items():
        full = root / rel
        if not full.exists():
            f.check(f"raw_lock.exists:{rel}", False, f"锁定后原始数据被删除: {rel}")
            continue
        actual = _sha256(full)
        declared = (meta.get("sha256") or "").lower()
        f.check(f"raw_lock.sha256:{rel}", actual == declared,
                f"{rel} 与锁定基线不符：锁定 {declared[:12]}… 实际 {actual[:12]}…"
                f"（原始数据在锁定后被改动）",
                ok_detail=f"{rel} 与 raw 锁定基线一致")


def verify_schema(payload: dict, root: Path, f: Findings,
                  require_schema: bool = False) -> None:
    """用 data_lineage.schema.json 做结构校验（原 schema 完全未被使用，属契约空转）。

    jsonschema 为可选依赖：装了才做结构校验，没装则记 WARN 不阻塞
    （语义层检查仍会跑，不致因缺库而失效）。

    require_schema=True（CLI --require-schema）时，jsonschema 缺失判 FAIL：
    契约明确要求结构校验，缺库不得静默降级——否则 minItems/enum/pattern/required
    在缺库环境里全部失效，把 stages[0].inputs 置空也能过。
    """
    schema_path = None
    here = Path(__file__).resolve().parent
    for cand in (
        here.parent / "shared" / "contracts" / "math_modeling" / "data_lineage.schema.json",
        root / "shared" / "contracts" / "math_modeling" / "data_lineage.schema.json",
    ):
        if cand.is_file():
            schema_path = cand
            break
    if schema_path is None:
        f.check("schema.present", False, "未找到 data_lineage.schema.json（结构契约缺失）",
                severity="WARN")
        return
    try:
        import jsonschema
    except ImportError:
        if require_schema:
            f.check("schema.enforced", False,
                    "要求结构校验（--require-schema）但未安装 jsonschema："
                    "minItems/enum/pattern/required 无法生效——pip install jsonschema")
        else:
            f.check("schema.enforced", False,
                    "未安装 jsonschema，跳过结构校验（pip install jsonschema 可启用）",
                    severity="WARN", ok_detail="结构校验已启用")
        return
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(payload)
        f.check("schema.enforced", True, "", ok_detail="符合 data_lineage.schema.json 结构契约")
    except jsonschema.ValidationError as exc:
        loc = "/".join(str(p) for p in exc.absolute_path) or "(root)"
        f.check("schema.enforced", False,
                f"结构契约不符（{loc}）：{exc.message[:160]}")
    except (json.JSONDecodeError, OSError) as exc:
        f.check("schema.enforced", False, f"schema 读取/解析失败: {exc}", severity="WARN")


def verify_invariants(payload: dict, f: Findings) -> None:
    inv = payload.get("invariants") or {}
    f.check("inv.raw_unmodified", inv.get("raw_unmodified") is True,
            "invariants.raw_unmodified 未声明为 true（原始数据只读性未被确认）",
            ok_detail="原始数据只读性已确认")
    f.check("inv.chain_continuous", inv.get("chain_continuous") is True,
            "invariants.chain_continuous 未声明为 true（血缘链连续性未被确认）",
            ok_detail="血缘链连续性已确认")
    if inv.get("reproducible") is False:
        f.check("inv.reproducible", False, "处理过程被标记为不可复现", severity="WARN")


def verify_thresholds(payload: dict, root: Path, f: Findings) -> None:
    """执行 D1 声明但此前无人读取的阈值：lineage_levels / rows_per_column_min。"""
    stages = payload.get("stages") or []
    names = {s.get("stage") for s in stages}
    if "processed" not in names:
        f.check("levels.processed", False, "缺少 processed 阶段——原始数据未经过任何清洗")
    for lvl in ("feature", "test_result"):
        if lvl not in names:
            f.check(f"levels.{lvl}", False,
                    f"缺少 {lvl} 阶段（如确实不涉及，请在 notes 说明理由）", severity="WARN")
    for item in (payload.get("raw") or {}).get("files") or []:
        rows, cols = item.get("rows"), item.get("cols")
        if isinstance(rows, int) and isinstance(cols, int) and cols > 0:
            need = cols * 3
            f.check(f"rows_per_col:{item.get('path')}", rows >= need,
                    f"{item.get('path')} 行数 {rows} < 列数 {cols}×3={need}"
                    f"（样本量相对特征维度不足，易过拟合）", severity="WARN")


def main() -> int:
    ap = argparse.ArgumentParser(description="数据血缘校验（D1 门禁机器执行者）")
    ap.add_argument("ledger", nargs="?", type=Path, help="data-lineage.json 路径")
    ap.add_argument("--root", type=Path, default=Path("."), help="项目根目录")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--check-raw", action="store_true", help="只校验 raw 是否被改动（快速）")
    ap.add_argument("--require-schema", action="store_true",
                    help="结构校验必需：jsonschema 不可用时判 FAIL（默认仅 WARN）")
    args = ap.parse_args()

    if not args.ledger or not args.ledger.exists():
        print(f"血缘台账不存在: {args.ledger}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(args.ledger.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"血缘台账 JSON 无效: {exc}", file=sys.stderr)
        return 2

    missing = [k for k in _required_top(args.root) if k not in payload]
    if missing:
        print(f"血缘台账缺少必填字段: {missing}", file=sys.stderr)
        return 2

    f = Findings()
    verify_raw(payload, args.root, f)
    verify_raw_lock(payload, args.root, f)
    verify_schema(payload, args.root, f, require_schema=args.require_schema)
    if not args.check_raw:
        verify_stages(payload, args.root, f)
        verify_invariants(payload, f)
        verify_thresholds(payload, args.root, f)
        verify_environment_lock(payload, args.root, f)

    out = f.result()
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"数据血缘校验：{out['status']}")
        for c in out["checks"]:
            mark = "✓" if c["status"] == "PASS" else ("!" if c["status"] == "WARN" else "✗")
            print(f"  {mark} {c['id']}: {c['detail']}")
        if out["warnings"]:
            print(f"\n警告 {len(out['warnings'])} 条（不阻断）")
        if out["errors"]:
            print(f"\n失败 {len(out['errors'])} 条")
    return 0 if out["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
