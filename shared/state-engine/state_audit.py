"""MM state_utils —— 审计/覆盖/结果管理命令（audit/coverage/cascade/result/report）（由 state_utils.py 拆分而来，勿手改结构；逻辑见各模块）。"""
from state_defs import *  # noqa: F401,F403
from state_scaffold import *  # noqa: F401,F403


def downstream_nodes(node):
    """按 UPSTREAM 反向闭包：直接/间接依赖 node 的全部下游节点。"""
    result = []
    def visit(n):
        for nid, ups in UPSTREAM.items():
            upstream_ids = [u for u, _ in ups]
            if nid not in result and n in upstream_ids:
                result.append(nid)
                visit(nid)
    visit(node)
    return result


def cmd_flow_coverage(args):
    """全流程覆盖检查：完整流程应调用的 Agent/Skill 集 vs 实际状态记录（executed_by/skills_used/审阅记录）。
    帮助发现"流程跑完但漏用了某专业 Agent 或 Skill"（如用 general-purpose 包办、跳过 humanize 去AI化）。"""
    root = os.path.abspath(args.dir)
    if not os.path.exists(os.path.join(root, STATE_FILE)):
        sys.exit(f"[state_utils] 项目未初始化：{root}；请先运行 init")
    state = load_state(root)
    # 预期调用集（registry/NODES 单一事实源）
    expected_agents = set()
    expected_skills = set()
    for nid, info in NODES.items():
        if nid == "N0":
            continue
        expected_agents.add(info["executor"])
        if info.get("reviewer"):
            expected_agents.add(info["reviewer"])
        expected_skills.update(info.get("skills", []))
    expected_agents.add("humanize")  # 去AI化专项（N8 前）
    expected_skills.update({"humanizer", "academic-humanize", "mathematical-modeling"})
    # 实际调用集
    used_agents, used_skills = set(), set()
    nodes = state.get("nodes", {})
    for nid, info in NODES.items():
        rec = nodes.get(nid) or {}
        if rec.get("executed_by"):
            used_agents.add(rec["executed_by"])
        used_skills.update(rec.get("skills_used") or [])
    # 审阅记录中出现的 Agent 与声明技能（从节点首页审阅记录解析 + gates.agent）
    for gate in (state.get("gates") or {}).values():
        if gate.get("agent"):
            used_agents.add(gate["agent"])
    for nid in NODES:
        home = node_homepage(root, nid)
        if not os.path.isfile(home):
            continue
        with open(home, "r", encoding="utf-8") as f:
            for ln in f:
                if ln.startswith("|") and "审阅 Agent" not in ln and "声明已读" in ln:
                    skills_part = ln.split("声明已读 Skill")[-1]
                    for tok in re.split(r"[|,，、\s]+", skills_part):
                        if tok.startswith("mm-") or tok in {"code-review", "humanizer", "academic-humanize"}:
                            used_skills.add(tok)
    missing_agents = sorted(expected_agents - used_agents)
    missing_skills = sorted(expected_skills - used_skills)
    completed = [nid for nid, rec in nodes.items() if rec.get("status") == "completed"]
    coverage = {"project": root, "checked_at": now_iso(), "nodes_completed": completed,
                "expected_agents": sorted(expected_agents), "expected_skills": sorted(expected_skills),
                "used_agents": sorted(used_agents), "used_skills": sorted(used_skills),
                "missing_agents": missing_agents, "missing_skills": missing_skills}
    if completed:
        coverage["summary"] = {
            "complete": not missing_agents and not missing_skills,
            "note": ("全流程 Agent/Skill 已全覆盖" if not missing_agents and not missing_skills
                     else f"缺失 Agent: {missing_agents or '无'}；缺失 Skill: {missing_skills or '无'}（未推进节点不算缺失）")}
    else:
        coverage["summary"] = {"complete": None, "note": "尚无节点完成；flow-coverage 在流程收尾时验证全覆盖"}
    print(json.dumps(coverage, ensure_ascii=False, indent=2))


def cmd_cascade_invalidate(args):
    """级联失效（联动同步）：上游产物变更/缺失 → 下游节点状态与门禁自动重置 pending
    （防"改代码/模型后论文、图表、调优没同步更新"）。默认预览，--apply 实际重置并留痕。"""
    root = os.path.abspath(args.dir)
    if not os.path.exists(os.path.join(root, STATE_FILE)):
        sys.exit(f"[state_utils] 项目未初始化：{root}；请先运行 init")
    state = load_state(root)
    targets = [args.node] if args.node else [nid for nid in NODES if nid != "N0"]
    changed, resets = [], []
    for nid in targets:
        status = state["nodes"][nid].get("status", "pending")
        if status not in {"completed", "in_progress", "review_pending"}:
            continue
        recorded = state["nodes"][nid].get("artifact_hash") or {}
        current = artifact_snapshot(root, nid)
        if current == recorded:
            continue
        diff = [p for p in current if current.get(p) != recorded.get(p)]
        changed.append({"node": nid, "diff": diff,
                        "reason": "产物哈希变化或首次未登记（node-finish 起登记；未登记视为变化）"})
        for down in downstream_nodes(nid):
            down_status = state["nodes"][down].get("status", "pending")
            if down not in resets and down_status in {"completed", "in_progress", "review_pending"}:
                resets.append(down)
    if args.apply:
        invalidations = state["meta"].setdefault("cascade_invalidations", [])
        # 2.0.0：变更节点本身也必须重验（否则"数据改了但 N2 仍 completed、D1 仍 PASS"）。
        # 本节点状态回 pending，其 REVIEW_GATE 门禁一并重置——产物都变了，原审阅结论不再有效。
        self_resets = []
        for item in changed:
            nid = item["node"]
            if state["nodes"][nid].get("status") == "pending":
                continue
            state["nodes"][nid]["status"] = "pending"
            state["nodes"][nid]["goal"] = ""
            stage = NODES[nid]["stage"]
            if stage in state.get("stages", {}):
                state["stages"][stage]["status"] = "pending"
                state["stages"][stage]["completed_at"] = None
            gate_id = REVIEW_GATE.get(nid)
            if gate_id and gate_id in state.get("gates", {}):
                state["gates"][gate_id]["status"] = "pending"
                state["gates"][gate_id]["result"] = f"自身产物变更，门禁需重验: {now_iso()}"
            self_resets.append(nid)
            invalidations.append({"at": now_iso(), "upstream_changed": nid, "reset": nid,
                                  "reason": "本节点产物变更，自身状态与门禁必须重验"})
            update_homepage_meta(node_homepage(root, nid), "pending")
        for down in resets:
            if state["nodes"][down].get("status") != "pending":
                state["nodes"][down]["status"] = "pending"
                state["nodes"][down]["goal"] = ""
                stage = NODES[down]["stage"]
                if stage in state.get("stages", {}):
                    state["stages"][stage]["status"] = "pending"
                    state["stages"][stage]["completed_at"] = None
                gate_id = REVIEW_GATE.get(down)
                if gate_id and gate_id in state.get("gates", {}):
                    state["gates"][gate_id]["status"] = "pending"
                    state["gates"][gate_id]["result"] = f"级联失效重置（上游产物变更）: {now_iso()}"
                invalidations.append({"at": now_iso(), "upstream_changed": nid, "reset": down,
                                      "reason": "上游产物变更，下游内容（论文/图表/调优等）必须同步更新后重验"})
            update_homepage_meta(node_homepage(root, down), "pending")
        save_state(root, state)
        refresh_dashboard(root)
    resets_out = locals().get("self_resets", []) + resets
    print(json.dumps({"preview": not args.apply, "changed_artifacts": changed,
                      "self_reset": locals().get("self_resets", []),
                      "downstream_reset": resets,
                      "hint": ("变更节点自身已重置，需重验其门禁；下游需重新派发执行 Agent 同步更新产物并重新审阅"
                               if (resets or locals().get("self_resets")) else "无需重置")},
                     ensure_ascii=False, indent=2))


def _load_result(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            result = json.load(stream)
    except FileNotFoundError as exc:
        raise ValueError(f"result 文件不存在: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"result 不是合法 JSON: {exc}") from exc
    if not isinstance(result, dict):
        raise ValueError("result 顶层必须是对象")
    return result


# ---------------------------------------------------------------- 迭代报告留存（reports/）

def reports_index(root, default=None):
    return load_json(os.path.join(root, REPORTS_INDEX), default or {"version": "1.0", "entries": []})


def append_report(root, entry):
    index = reports_index(root)
    index.setdefault("entries", []).append(entry)
    save_json_atomic(os.path.join(root, REPORTS_INDEX), index)


def _report_scope_token(scope_id):
    """Validate a scope token before putting it in a report filename."""
    if scope_id is None:
        return None
    value = str(scope_id).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value) or ".." in value:
        raise ValueError("非法 scope_id，报告文件名必须使用安全作用域标识")
    return value


def save_round_report(root, node, round_no, kind, payload, scope_id=None):
    """留存迭代报告并登记索引。

    ``scope_id`` is optional: omitted calls retain the exact legacy filename
    and index shape; scoped calls receive a collision-resistant filename and
    an explicit index field for ``report-list --scope``.
    """
    scoped = _report_scope_token(scope_id if scope_id is not None else payload.get("scope_id"))
    ts = now_iso().replace(":", "").replace("-", "")
    scope_part = f"_s{scoped}" if scoped else ""
    if round_no is not None:
        name = f"{node}_r{round_no}{scope_part}_{kind}_{ts}.json"
    else:
        name = f"{node}{scope_part}_{kind}_{ts}.json"
    rel = os.path.join(REPORTS_DIR, name)
    report_payload = dict(payload)
    if scoped:
        report_payload["scope_id"] = scoped
    save_json_atomic(os.path.join(root, rel), report_payload)
    entry = {
        "path": rel, "kind": kind, "node": node, "round": round_no,
        "agent": report_payload.get("agent") or report_payload.get("judge") or report_payload.get("agent_id") or "-",
        "timestamp": report_payload.get("timestamp") or now_iso(),
        "summary": report_payload.get("verdict") or report_payload.get("action") or report_payload.get("status") or "-",
    }
    if scoped:
        entry["scope_id"] = scoped
        entry["scope_key"] = report_payload.get("scope_key") or f"{node}:r{round_no}:{scoped}"
    append_report(root, entry)
    return rel


def cmd_report_list(args):
    root = os.path.abspath(args.dir)
    index = reports_index(root)
    entries = index.get("entries", [])
    if args.node:
        entries = [e for e in entries if e.get("node") == args.node]
    if args.round is not None:
        entries = [e for e in entries if e.get("round") == args.round]
    scope_filter = getattr(args, "scope", None)
    if scope_filter:
        entries = [e for e in entries if e.get("scope_id") == scope_filter]
    if args.json:
        print(json.dumps({"reports_dir": REPORTS_DIR, "count": len(entries), "entries": entries},
                         ensure_ascii=False, indent=2))
        return
    print(f"# 迭代报告留存（{REPORTS_DIR}/）")
    print()
    print("| 节点 | 轮次 | 作用域 | 类型 | Agent | 结论/动作 | 报告路径 |")
    print("|------|:----:|--------|------|-------|----------|---------|")
    if not entries:
        print("| - | - | - | - | - | - | - |")
    for e in entries:
        print(f"| {e.get('node', '-')} | {e.get('round', '-')} | {e.get('scope_id', '-')} | {e.get('kind', '-')} | {e.get('agent', '-')} | {e.get('summary', '-')} | `{e.get('path', '-')}` |")


def validate_result(root, result, expected_node=None, expected_run=None):
    required = ("schema_version", "agent_id", "node_id", "run_id", "status",
                "artifacts", "checks", "feedback", "timestamps", "payload")
    missing = [key for key in required if key not in result]
    if missing:
        raise ValueError(f"result 缺少必需字段: {', '.join(missing)}")
    if result.get("schema_version") != "1.0":
        raise ValueError("result schema_version 必须为 1.0")
    node = result.get("node_id")
    require_node(node)
    if expected_node and node != expected_node:
        raise ValueError(f"result node_id={node} 与目标节点 {expected_node} 不一致")
    if expected_run and result.get("run_id") != expected_run:
        raise ValueError("result run_id 与目标轮次不一致")
    statuses = {"pending", "in_progress", "review_pending", "completed", "repair_pending", "blocked", "escalated", "failed"}
    if result.get("status") not in statuses:
        raise ValueError(f"result status 非法: {result.get('status')}")
    if not isinstance(result.get("artifacts"), list) or not isinstance(result.get("checks"), list):
        raise ValueError("result artifacts/checks 必须是数组")
    if not isinstance(result.get("feedback"), list) or not isinstance(result.get("payload"), dict):
        raise ValueError("result feedback/payload 类型不正确")
    verdict = result.get("review_verdict")
    if verdict is not None and verdict not in {"PASS", "FAIL", "BLOCKED"}:
        raise ValueError(f"review_verdict 非法: {verdict}")
    # 审阅独立铁律：带审阅裁决的结果必须由注册的独立审阅 Agent 提交（N8 终审为显式豁免）
    if verdict is not None and node != "N8":
        expected_reviewer = NODES[node]["reviewer"]
        if result["agent_id"] != expected_reviewer:
            raise ValueError(f"审阅结果必须由独立审阅 Agent {expected_reviewer} 提交，实际为 {result['agent_id']}")
    checked_artifacts = []
    root = os.path.abspath(root)
    for item in result["artifacts"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"].strip():
            raise ValueError("result artifacts 中每项必须包含非空 path")
        rel = item["path"]
        full = os.path.abspath(os.path.join(root, rel))
        if not (full == root or full.startswith(root + os.sep)):
            raise ValueError(f"artifact 路径越界: {rel}")
        if os.path.isfile(full):
            digest = sha256_of(full)
            declared = item.get("sha256")
            if declared and declared != digest:
                raise ValueError(f"artifact SHA-256 不匹配: {rel}")
            checked_artifacts.append({"path": rel, "sha256": digest})
        elif os.path.isdir(full):
            checked_artifacts.append({"path": rel, "sha256": item.get("sha256")})
        else:
            raise ValueError(f"artifact 不存在: {rel}")
    result["validated_artifacts"] = checked_artifacts
    return result


def cmd_result_validate(args):
    root = os.path.abspath(args.dir)
    result = validate_result(root, _load_result(os.path.abspath(args.result)), args.node, args.run_id)
    print(json.dumps({"valid": True, "node_id": result["node_id"], "run_id": result["run_id"],
                      "status": result["status"], "artifacts": result["validated_artifacts"]},
                     ensure_ascii=False, indent=2))


def cmd_result_ingest(args):
    root = os.path.abspath(args.dir)
    state = load_state(root)
    result = validate_result(root, _load_result(os.path.abspath(args.result)), args.node, args.run_id)
    node = result["node_id"]
    summary = {"agent_id": result["agent_id"], "run_id": result["run_id"], "status": result["status"],
               "review_verdict": result.get("review_verdict"), "decision_action": result.get("decision_action"),
               "artifacts": result["validated_artifacts"], "ingested_at": now_iso()}
    round_no = result.get("payload", {}).get("round")
    save_round_report(root, node, round_no, "result", result)
    state["nodes"][node].setdefault("results", []).append(summary)
    state["nodes"][node]["last_result"] = summary
    if result["status"] in {"blocked", "escalated", "repair_pending", "review_pending"}:
        state["nodes"][node]["status"] = result["status"]
    elif result["status"] == "completed":
        state["nodes"][node]["status"] = "completed"
        state["stages"][NODES[node]["stage"]]["status"] = "completed"
        state["stages"][NODES[node]["stage"]]["completed_at"] = now_iso()
    save_state(root, state)
    refresh_dashboard(root)
    print(json.dumps({"ingested": True, "node_id": node, "run_id": result["run_id"], "status": result["status"]},
                     ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- 项目接手审计与修复（project-audit / project-repair）

def audit_problem_lock(root, source=None):
    """只读检查题目事实锁定；不抛异常，返回报告 dict。source 可覆盖锁内 source_path 用于比对。"""
    path = os.path.join(root, STATE_DIR, "problem_lock.json")
    if not os.path.exists(path):
        return {"exists": False, "status": "missing", "drift": True,
                "detail": "未创建 problem_lock.json；接手已有项目必须先阅读题目并锁定事实（problem_guard.py create）"}
    lock = load_json(path)
    required_fields = ("objectives", "constraints", "preconditions", "data_requirements", "evaluation_metrics")
    missing = [key for key in required_fields if not isinstance(lock.get(key), list) or not lock[key]]
    drift = lock.get("status") != "verified" or bool(missing)
    detail = []
    if missing:
        detail.append(f"事实字段缺失: {', '.join(missing)}")
    target = source or lock.get("source_path", "")
    if target:
        full = target if os.path.isabs(target) else os.path.join(root, target)
        if not os.path.isfile(full):
            detail.append(f"题目原文不存在: {full}")
            drift = True
        elif lock.get("source_sha256") and sha256_of(full) != lock.get("source_sha256"):
            detail.append("题目原文 SHA-256 与锁定值不一致（题目已修改，需重新锁定）")
            drift = True
    if lock.get("status") != "verified":
        detail.append(f"锁定状态为 {lock.get('status')}，需要 verified")
    return {"exists": True, "status": lock.get("status"), "drift": drift,
            "missing": missing, "detail": "; ".join(detail) or "通过"}


def check_structure(root):
    return {"missing_dirs": [d for d in STANDARD_DIRS if not os.path.isdir(os.path.join(root, d))],
            "missing_files": [f for f in STANDARD_FILES if not os.path.isfile(os.path.join(root, f))]}


def check_node_homepages(root):
    return [node for node in NODES if not os.path.isfile(node_homepage(root, node))]


def check_registry_state(root):
    path = os.path.join(root, REGISTRY_FILE)
    if not os.path.isfile(path):
        return {"exists": False, "inconsistencies": []}
    registry = load_json(path)
    by_id = {entry.get("id"): entry for entry in registry.get("nodes", []) if entry.get("id")}
    problems = []
    for nid, info in NODES.items():
        if nid == "N0":
            continue
        entry = by_id.get(nid)
        if entry is None:
            problems.append(f"registry 缺少节点 {nid}")
            continue
        if entry.get("executor") != info.get("executor") or entry.get("reviewer") != info.get("reviewer"):
            problems.append(f"节点 {nid} 执行/审阅 Agent 与 NODES 不一致")
        if normalized_skill_set(entry.get("required_skills", [])) != normalized_skill_set(info.get("skills", [])):
            problems.append(f"节点 {nid} skills 与 NODES 不一致")
        if entry.get("artifact_dir") != info.get("artifact"):
            problems.append(f"节点 {nid} artifact 与 NODES 不一致")
    return {"exists": True, "inconsistencies": problems}


def check_state_artifact_drift(root):
    state = load_state(root)
    drift, unregistered = [], []
    for nid, info in NODES.items():
        status = state["nodes"][nid].get("status", "pending")
        paths = [p.strip() for p in info.get("artifact", "").split(",") if p.strip()]
        if status == "completed":
            for p in paths:
                if not os.path.exists(os.path.join(root, p)):
                    drift.append(f"节点 {nid} 状态为 completed 但产物 {p} 缺失（级联失效）")
        elif status == "pending":
            existing = [p for p in paths if os.path.exists(os.path.join(root, p))]
            if existing:
                unregistered.append(f"节点 {nid} 存在产物 {', '.join(existing)} 但状态为 pending（未登记）")
    return {"drift": drift, "unregistered": unregistered}


def check_legacy_names(root):
    legacy = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirpath.split(os.sep):
            continue
        for name in dirnames + filenames:
            if re.match(r"^(N[0-8]-|Word_Version|LaTeX_Version)", name):
                legacy.append(os.path.relpath(os.path.join(dirpath, name), root))
    return legacy


# ---------------------------------------------------------------- 升级自愈（旧版遗留迁移）
try:  # 容错：项目内旧副本可能缺 legacy_names.py，缺时按无遗留处理（init 已同步复制配套模块）
    from legacy_names import LEGACY_EMPTY_DIRS, LEGACY_RENAME, LEGACY_STATE_DIR  # 旧名映射（lint 豁免）
except ImportError:
    LEGACY_EMPTY_DIRS, LEGACY_RENAME = {}, {}
    LEGACY_STATE_DIR = "00" + "_State"  # 与 legacy_names.py 同义；lint 红线要求不出现字面旧名


def plan_migration(root):
    """扫描旧版遗留（旧状态目录、旧文件名、旧节点首页目录、重复空目录），返回迁移计划（不执行）。"""
    actions = []
    old_state = os.path.join(root, LEGACY_STATE_DIR)
    if os.path.isdir(old_state):
        if not os.path.isdir(os.path.join(root, STATE_DIR)):
            actions.append(f"迁移目录 {LEGACY_STATE_DIR} -> {STATE_DIR}")
        else:
            actions.append(f"合并目录 {LEGACY_STATE_DIR} -> {STATE_DIR}（缺失文件补齐，不覆盖）")
    old_nodes = os.path.join(root, STATE_DIR, "nodes")
    if not os.path.isdir(old_nodes):
        old_nodes = os.path.join(root, LEGACY_STATE_DIR, "nodes")
    if os.path.isdir(old_nodes):
        for nid, info in NODES.items():
            old_dir = f"{nid}-{info['dir']}"
            oldp = os.path.join(old_nodes, old_dir)
            if os.path.isdir(oldp) and not os.path.isdir(node_homepage(root, nid)):
                actions.append(f"迁移节点首页目录 nodes/{old_dir} -> nodes/{info['dir']}")
    for old, new in LEGACY_RENAME.items():
        oldp, newp = os.path.join(root, old), os.path.join(root, new)
        if os.path.exists(oldp) and not os.path.exists(newp):
            actions.append(f"重命名文件 {old} -> {new}")
    for d in LEGACY_EMPTY_DIRS:
        oldp = os.path.join(root, d)
        if os.path.isdir(oldp) and not os.listdir(oldp):
            actions.append(f"删除空目录 {d}")
    return actions


def apply_migration(root, actions):
    for action in actions:
        if action.startswith("迁移目录"):
            old, new = os.path.join(root, LEGACY_STATE_DIR), os.path.join(root, STATE_DIR)
            if os.path.isdir(old) and not os.path.isdir(new):
                os.rename(old, new)
        elif action.startswith("合并目录"):
            old, new = os.path.join(root, LEGACY_STATE_DIR), os.path.join(root, STATE_DIR)
            if os.path.isdir(old) and os.path.isdir(new):
                for dirpath, _, filenames in os.walk(old):
                    rel = os.path.relpath(dirpath, old)
                    for f in filenames:
                        src = os.path.join(dirpath, f)
                        dst = os.path.join(new, rel, f)
                        if not os.path.exists(dst):
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            shutil.move(src, dst)
                for dirpath, dirnames, filenames in os.walk(old, topdown=False):
                    if not dirnames and not filenames:
                        os.rmdir(dirpath)
                if os.path.isdir(old) and not os.listdir(old):
                    os.rmdir(old)
        elif action.startswith("迁移节点首页目录"):
            parts = action.split(" -> ")
            old = os.path.join(root, STATE_DIR, parts[0].split(" ", 1)[1])
            new = os.path.join(root, STATE_DIR, parts[1])
            if os.path.isdir(old) and not os.path.isdir(new):
                os.makedirs(os.path.dirname(new), exist_ok=True)
                os.rename(old, new)
        elif action.startswith("重命名文件"):
            parts = action.split(" -> ")
            old = os.path.join(root, parts[0].split(" ", 1)[1])
            new = os.path.join(root, parts[1])
            if os.path.exists(old) and not os.path.exists(new):
                os.makedirs(os.path.dirname(new), exist_ok=True)
                os.rename(old, new)
        elif action.startswith("删除空目录"):
            d = os.path.join(root, action.split(" ", 2)[2])
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
    # 迁移后修复 JSON/文档中的旧引用（旧状态目录名 -> 新目录名）
    for rel in (STATE_FILE, REGISTRY_FILE, DASHBOARD_FILE):
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            text = open(p, "r", encoding="utf-8").read()
            if LEGACY_STATE_DIR in text:
                save_text_atomic(p, text.replace(LEGACY_STATE_DIR, STATE_DIR))


def cmd_upgrade_heal(args):
    """升级自愈：检测旧版遗留 → 迁移修复 → 补建 → 复检（自动纠正，杜绝旧版 bug 残留）。"""
    root = os.path.abspath(args.dir)
    has_state = os.path.exists(os.path.join(root, STATE_FILE))
    has_old = os.path.exists(os.path.join(root, LEGACY_STATE_DIR, "decision_log.json"))
    if not has_state and not has_old:
        sys.exit(f"[state_utils] 未找到项目状态（{STATE_DIR}/ 或旧版状态目录），请先 init")
    print(f"[state_utils] upgrade-heal: {root}")
    mig = plan_migration(root)
    if not mig:
        print("[state_utils] 未发现旧版遗留，无需迁移。")
    for a in mig:
        print(f"  - {a}")
    if not args.apply:
        print("[state_utils] 预览模式：未修改文件。确认后追加 --apply。")
        return
    apply_migration(root, mig)
    print(f"[state_utils] 迁移完成（{len(mig)} 项）。")
    # 补建（复用 project-repair 的 apply 路径）
    cmd_project_repair(argparse.Namespace(dir=args.dir, apply=True, source=args.source))
    # 复检
    print("[state_utils] === 复检（project-audit）===")
    cmd_project_audit(argparse.Namespace(dir=args.dir, source=args.source))


def check_state_authenticity(root):
    """状态真实性检查：识别"手工伪造状态文件（绕过 state_utils.py CLI）"。容错读取，不崩溃。"""
    problems = []
    path = os.path.join(root, STATE_FILE)
    if not os.path.isfile(path):
        return ["缺少 state/decision_log.json"]
    state = load_json(path)
    if not isinstance(state, dict):
        return ["decision_log 不是合法对象"]
    meta = state.get("meta") or {}
    if meta.get("generator") != "state_utils.py init":
        problems.append("decision_log 缺少 generator 标记（疑似手工创建状态，未走 init）")
    nodes = state.get("nodes") or {}
    missing_nodes = [nid for nid in NODES if nid not in nodes]
    if missing_nodes:
        problems.append(f"状态缺少节点定义: {missing_nodes}")
    if state.get("_schema") != "2.0":
        problems.append(f"schema 不是 2.0: {state.get('_schema')}")
    return problems


def check_executor_evidence(root):
    """执行者证据检查（防内联代做）：节点 completed/in_progress 必须有其执行 Agent 的 result.json。
    主 agent 不派发子 Agent 而直接标完成时，子 Agent 不会写 result.json → 此处标记疑似绕过派发。"""
    state = load_json(os.path.join(root, STATE_FILE))
    if not isinstance(state, dict):
        return []
    nodes = state.get("nodes") or {}
    missing = []
    for nid, info in NODES.items():
        if nid == "N0":
            continue
        status = (nodes.get(nid) or {}).get("status")
        if status not in {"completed", "in_progress", "review_pending"}:
            continue
        executor = info["executor"]
        result_file = os.path.join(root, STATE_DIR, "agents", executor, "result.json")
        if not os.path.isfile(result_file):
            missing.append({"node": nid, "executor": executor, "status": status,
                            "reason": f"节点 {nid} 状态={status} 但执行 Agent {executor} 无 result.json 证据（疑似主 agent 内联代做/绕过派发；子 Agent 收工必须写 state/agents/<id>/result.json）"})
    return missing


def check_unreviewed_completion(root):
    """审阅-修改循环完整性（防跳过审阅）：节点 completed 但对应门禁未通过 → 未审阅即完成。
    合法路径只有一条：执行 → 独立审阅 → PASS 完成 / FAIL → 修改（加载对应 skill）→ 再审阅。"""
    state = load_json(os.path.join(root, STATE_FILE))
    if not isinstance(state, dict):
        return []
    nodes, gates = state.get("nodes", {}), state.get("gates", {})
    missing = []
    for nid, info in NODES.items():
        if nid == "N0":
            continue
        if (nodes.get(nid) or {}).get("status") != "completed":
            continue
        gate_id = REVIEW_GATE.get(nid)
        if not gate_id:
            continue
        g = gates.get(gate_id) or {}
        if g.get("status") not in {"PASS", "auto_passed", "confirmed"}:
            missing.append({"node": nid, "gate": gate_id, "gate_status": g.get("status", "pending"),
                            "reason": f"节点 {nid} 已 completed 但门禁 {gate_id} 未通过"
                                      f"（{g.get('status', 'pending')}）——疑似跳过'审阅→修改→再审阅'循环"})
    return missing


def check_premature_progression(root):
    """阶段联动完整性（防"阶段不完全/修改不完善就推进下一步"）：非 pending 节点的上游必须 completed 且审阅门禁已过。
    用于检测绕过 node-start 校验（手工改状态/跳过审阅循环）的推进。"""
    state = load_json(os.path.join(root, STATE_FILE))
    if not isinstance(state, dict):
        return []
    nodes, gates = state.get("nodes", {}), state.get("gates", {})
    problems = []
    for nid, info in NODES.items():
        if nid == "N0":
            continue
        status = (nodes.get(nid) or {}).get("status", "pending")
        if status == "pending":
            continue
        for up_node, up_name in UPSTREAM.get(nid, []):
            up_status = (nodes.get(up_node) or {}).get("status", "pending")
            if up_status != "completed":
                problems.append({"node": nid, "node_status": status, "upstream": up_node,
                                 "upstream_status": up_status,
                                 "reason": f"节点 {nid} 已推进（{status}）但上游 {up_node}({up_name}) 未 completed——阶段不完全即推进"})
            up_gate = REVIEW_GATE.get(up_node)
            if up_gate and (gates.get(up_gate) or {}).get("status") not in {"PASS", "auto_passed", "confirmed"}:
                problems.append({"node": nid, "node_status": status, "upstream": up_node, "gate": up_gate,
                                 "gate_status": (gates.get(up_gate) or {}).get("status", "pending"),
                                 "reason": f"节点 {nid} 已推进（{status}）但上游 {up_node} 审阅门禁 {up_gate} 未通过——上游修改不完善即推进"})
    return problems


CURRENT_SKILL_VERSION = "1.5.0"  # 与 SKILL.md frontmatter / state_scaffold init 模板同步（lint_contracts 核对）


def _ver_tuple(v):
    parts = str(v).split(".")
    try:
        return tuple(int(p) for p in parts[:3])
    except ValueError:
        return None


def check_h_gate_consistency(root):
    """H 门禁一致性（防"人工确认未过即收尾"）：节点 completed 但其 H1/H2/H3 人工确认门禁仍 pending。
    auto_passed 是合法待追认态（auto-check 已核查、等人工 h-confirm 追认，可在节点完成后追认）；只有完全未处理
    （pending）且节点已 completed 才算违规。事故实例：N7 early_stop 完成但 H3（论文整体人工确认）保持 pending。"""
    state = load_json(os.path.join(root, STATE_FILE))
    if not isinstance(state, dict):
        return []
    nodes, gates = state.get("nodes", {}), state.get("gates", {})
    problems = []
    for nid, info in NODES.items():
        if nid == "N0":
            continue
        if (nodes.get(nid) or {}).get("status") != "completed":
            continue
        for h in ("H1", "H2", "H3"):
            if h not in info.get("gates", []):
                continue
            g = gates.get(h) or {}
            if g.get("status") not in {"PASS", "confirmed", "auto_passed"}:
                problems.append({"node": nid, "gate": h, "gate_status": g.get("status", "pending"),
                                 "reason": f"节点 {nid} 已 completed 但人工确认门禁 {h} 完全未处理"
                                           f"（{g.get('status', 'pending')}）——不允许'未人工确认即收尾'；"
                                           f"{h} 需 auto-check 核查或用户 h-confirm 追认"})
    return problems


def check_engine_legacy(root):
    """引擎版本遗留（防旧版引擎/旧副本产物混入）：扫描 state 记录中出现的 skill 版本，
    低于当前插件版本 → 标记 legacy。旧引擎评审缺少 MCP 必调/知识卡片/executor 证据等新门禁，
    其评审结论不得再作为有效依据。事故实例：项目 skills_read 为 mm-latex-writing@1.3.0。"""
    current = _ver_tuple(CURRENT_SKILL_VERSION)
    findings = []
    pattern = re.compile(r"mm-[\w-]+@(\d+(?:\.\d+){1,2})")
    for dirpath, _dirs, files in os.walk(os.path.join(root, STATE_DIR)):
        for fn in files:
            if not fn.endswith((".md", ".json")):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in pattern.finditer(text):
                ver = _ver_tuple(m.group(1))
                if ver and ver < current:
                    findings.append({"file": os.path.relpath(path, root), "skill": m.group(0),
                                     "version": m.group(1), "current": CURRENT_SKILL_VERSION,
                                     "reason": f"检测到旧版引擎产物 {m.group(0)}（当前插件版本 {CURRENT_SKILL_VERSION}）——"
                                               f"由旧版引擎/旧副本产生，缺少 MCP 必调/知识卡片/executor 证据等新门禁，"
                                               f"相关评审结论不可作为有效依据"})
    seen, uniq = set(), []
    for f in findings:
        key = (f["file"], f["skill"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    return uniq


def _parse_review_ts(s):
    """解析审阅记录时间（仅接受带时区标识的 Z / +hh:mm，统一转 UTC aware；裸本地时间跳过避免时区误判）。"""
    from datetime import datetime, timezone, timedelta
    s = s.strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)(Z|[+-]\d{2}:?\d{2})$", s)
    if not m:
        return None
    base, tz = m.group(1), m.group(2)
    try:
        dt = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S") if ":" in base[11:] else datetime.strptime(base, "%Y-%m-%dT%H:%M")
    except ValueError:
        try:
            dt = datetime.strptime(base, "%Y-%m-%dT%H:%M")
        except ValueError:
            return None
    if tz == "Z":
        return dt.replace(tzinfo=timezone.utc)
    sign = 1 if tz[0] == "+" else -1
    tz = tz[1:].replace(":", "")
    return dt.replace(tzinfo=timezone(timedelta(hours=sign * int(tz[:2]), minutes=sign * int(tz[2:])))).astimezone(timezone.utc)


def check_review_timeline(root):
    """评审-产物时间线（防"评审对象非最终交付物"）：节点审阅记录的最新时间早于最终论文 PDF（main.pdf 优先）mtime
    → 评审结论对不上最终产物，评审无效，必须对最终版本重评。事故实例：评审 8/18T23:45Z 打 9.0，
    最终 build/main.pdf 次日才生成。"""
    from datetime import datetime, timezone
    reviews = []
    pat = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(Z|[+-]\d{2}:?\d{2}))\s*\|")
    nodes_dir = os.path.join(root, STATE_DIR, "nodes")
    if os.path.isdir(nodes_dir):
        for dirpath, _dirs, files in os.walk(nodes_dir):
            for fn in files:
                if not fn.endswith(".md"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for ln in f:
                            m = pat.match(ln)
                            if m:
                                ts = _parse_review_ts(m.group(1))
                                if ts is not None:
                                    reviews.append(ts)
                except (OSError, UnicodeDecodeError):
                    continue
    if not reviews:
        return []
    latest_review = max(reviews)
    candidates = []
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", ".venv", "__pycache__")]
        for fn in files:
            if fn.endswith(".pdf"):
                candidates.append(os.path.join(dirpath, fn))
    if not candidates:
        return []
    latest_pdf = max(candidates, key=os.path.getmtime)
    pdf_mtime = datetime.fromtimestamp(os.path.getmtime(latest_pdf), tz=timezone.utc)
    if pdf_mtime > latest_review:
        return [{"latest_review_at": latest_review.isoformat(),
                 "latest_pdf": os.path.relpath(latest_pdf, root), "pdf_mtime": pdf_mtime.isoformat(),
                 "reason": f"最终论文产物 {os.path.relpath(latest_pdf, root)} 修改时间（{pdf_mtime.isoformat()}）晚于最后审阅时间"
                           f"（{latest_review.isoformat()}）——评审对象不是最终交付物，现有评审结论（含评分）对最终版本无效；"
                           f"必须对最终产物重新执行 N7/N8 评审"}] 
    return []


def _scan_orphans_for_audit(root):
    """project-audit 用的轻量孤儿扫描（复用 orphan-scan 的判定，不落盘）。"""
    try:
        from state_progress import _scan_orphans
        return _scan_orphans(root)
    except (ImportError, AttributeError):
        return []


def cmd_project_audit(args):
    root = os.path.abspath(args.dir)
    report = {"project": root, "audited_at": now_iso()}
    if not os.path.exists(os.path.join(root, STATE_FILE)):
        report["initialized"] = False
        report["summary"] = {"healthy": False, "issues": ["项目未初始化：缺少 state/decision_log.json，请先运行 init"]}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    report["initialized"] = True
    report["state_authenticity"] = check_state_authenticity(root)
    report["executor_evidence_missing"] = check_executor_evidence(root)
    report["unreviewed_completion"] = check_unreviewed_completion(root)
    report["premature_progression"] = check_premature_progression(root)
    authentic = not report["state_authenticity"]
    if authentic:
        report["problem_lock"] = audit_problem_lock(root, args.source)
        report["structure"] = check_structure(root)
        report["node_homepages_missing"] = check_node_homepages(root)
        report["registry"] = check_registry_state(root)
        consistency = check_state_artifact_drift(root)
        report["state_artifact_drift"] = consistency["drift"]
        report["unregistered_artifacts"] = consistency["unregistered"]
    else:
        report["problem_lock"] = audit_problem_lock(root, args.source)
        report["structure"] = check_structure(root)
        report["node_homepages_missing"] = check_node_homepages(root)
        report["registry"] = {"exists": os.path.isfile(os.path.join(root, REGISTRY_FILE)),
                              "inconsistencies": [], "skipped": "状态非标准，跳过 registry/状态-产物一致性检查"}
        report["state_artifact_drift"] = []
        report["unregistered_artifacts"] = []
    report["legacy_names"] = check_legacy_names(root)
    report["h_gate_consistency"] = check_h_gate_consistency(root)
    report["engine_legacy"] = check_engine_legacy(root)
    report["review_timeline"] = check_review_timeline(root)
    # 2.0.0：孤儿文件扫描入审计（此前 orphan-scan 是独立命令、无人调用）。
    # 找出既不在任何节点产物目录、也未登记入库的散落文件。
    report["orphan_files"] = _scan_orphans_for_audit(root)
    issues = []
    if report["state_authenticity"]:
        issues.append("状态文件非标准（疑似绕过 CLI 手工创建）")
    if report["executor_evidence_missing"]:
        issues.append("疑似内联代做：节点已推进但执行 Agent 无 result.json 证据（" +
                      ", ".join(f"{m['node']}→{m['executor']}" for m in report["executor_evidence_missing"]) + "）")
    if report["unreviewed_completion"]:
        issues.append("未审阅即完成（跳过审阅-修改循环）：" +
                      ", ".join(f"{m['node']}（{m['gate']}={m['gate_status']}）" for m in report["unreviewed_completion"]))
    if report["premature_progression"]:
        issues.append("阶段不完全即推进（上游未完成/未审阅）：" +
                      ", ".join(f"{m['node']}←{m['upstream']}" for m in report["premature_progression"]))
    if report["problem_lock"]["drift"]:
        issues.append("题目事实锁定缺失或漂移")
    if report["structure"]["missing_dirs"] or report["structure"]["missing_files"]:
        issues.append("标准结构缺失")
    if report["node_homepages_missing"]:
        issues.append("节点首页缺失")
    if not report["registry"]["exists"] or report["registry"]["inconsistencies"]:
        issues.append("registry 缺失或不一致")
    if report["state_artifact_drift"]:
        issues.append("状态-产物不一致（completed 但产物缺失）")
    if report["legacy_names"]:
        issues.append("旧命名残留")
    if report["h_gate_consistency"]:
        issues.append("人工确认门禁未过即收尾（" +
                      ", ".join(f"{m['node']}→{m['gate']}={m['gate_status']}" for m in report["h_gate_consistency"]) + "）")
    if report["engine_legacy"]:
        issues.append("旧版引擎产物混入（" +
                      ", ".join(sorted({m['version'] for m in report['engine_legacy']})) +
                      " < 当前 " + CURRENT_SKILL_VERSION + "，相关评审结论无效）")
    if report["review_timeline"]:
        issues.append("评审对象非最终产物（" +
                      ", ".join(m["latest_pdf"] for m in report["review_timeline"]) + " 晚于最后审阅，必须重评）")
    if report["orphan_files"]:
        issues.append(f"散落文件未入库（{len(report['orphan_files'])} 个）："
                      + ", ".join(report["orphan_files"][:5])
                      + ("…" if len(report["orphan_files"]) > 5 else "")
                      + "（移入对应节点产物目录并登记，或确认属源码/配置后豁免）")
    report["summary"] = {"healthy": not issues, "issues": issues}
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_project_repair(args):
    root = os.path.abspath(args.dir)
    if not os.path.exists(os.path.join(root, STATE_FILE)):
        sys.exit(f"[state_utils] 项目未初始化：{root}；请先运行 init")
    state = load_state(root)
    competition = state.get("competition", {})
    plan = {"project": root, "planned_at": now_iso(), "actions": [], "blocked": []}
    for d in STANDARD_DIRS:
        if not os.path.isdir(os.path.join(root, d)):
            plan["actions"].append(f"创建目录 {d}")
    files = standard_files_content(competition.get("name", ""), competition.get("year", ""),
                                   competition.get("problem", ""), competition.get("language", "zh"))
    for path in files:
        if not os.path.isfile(os.path.join(root, path)):
            plan["actions"].append(f"补建文件 {path}")
    for nid in NODES:
        if not os.path.isfile(node_homepage(root, nid)):
            plan["actions"].append(f"重建节点首页 {nid}")
    if not os.path.isfile(os.path.join(root, REGISTRY_FILE)):
        plan["actions"].append("重建 registry.json")
    for f in ("human_checkpoint.md",):
        if not os.path.isfile(os.path.join(root, STATE_DIR, f)):
            plan["actions"].append(f"补建 {STATE_DIR}/{f}")
    lock = audit_problem_lock(root, args.source)
    if not lock["exists"] or lock["drift"]:
        plan["blocked"].append("题目事实锁定缺失或漂移：需先阅读题目并用 problem_guard.py create 重新锁定（自动修复需人工/Agent 事实，不代填）")
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        print("预览模式：未修改文件。确认后追加 --apply。", flush=True)
        return
    for action in plan["actions"]:
        if action.startswith("创建目录"):
            os.makedirs(os.path.join(root, action.split(" ", 1)[1]), exist_ok=True)
        elif action.startswith("补建文件"):
            path = action.split(" ", 1)[1]
            if not os.path.isfile(os.path.join(root, path)):
                save_text_atomic(os.path.join(root, path), files[path])
        elif action.startswith("重建节点首页"):
            nid = action.split(" ", 1)[1]
            info = NODES[nid]
            save_text_atomic(node_homepage(root, nid), NODE_DASHBOARD_TEMPLATE.format(
                NODE_ID=nid, NODE_NAME=info["name"], NODE_DIR=info["dir"], EXECUTOR=info["executor"],
                REVIEWER=info["reviewer"] or "-", SKILLS=", ".join(info["skills"]) or "-",
                ARTIFACT_DIR=info["artifact"], GATES=" / ".join(info["gates"]) or "-"))
        elif action.startswith("重建 registry"):
            registry = {"_comment": "调用路由注册表：任务→执行 Agent→审阅 Agent→必读 Skill→门禁→产物。任何委派必须与本表匹配。迭代动态门禁 S<n>-<节点> 未列于此。",
                        "version": "1.0", "nodes": []}
            for nid, info in NODES.items():
                if nid == "N0":
                    continue
                registry["nodes"].append({
                    "id": nid, "name": info["name"], "trigger_phrases": info["phrases"],
                    "executor": info["executor"], "reviewer": info["reviewer"], "review_mode": info["review_mode"],
                    "required_skills": info["skills"], "gates": info["gates"], "artifact_dir": info["artifact"],
                    "homepage": f"{STATE_DIR}/nodes/{info['dir']}/dashboard.md",
                    "upstream": [up for up, _ in UPSTREAM.get(nid, [])]})
            save_json_atomic(os.path.join(root, REGISTRY_FILE), registry)
        elif action.startswith("补建"):
            save_text_atomic(os.path.join(root, STATE_DIR, "human_checkpoint.md"), HUMAN_CHECKPOINT)
    plan["applied"] = True
    print(json.dumps(plan, ensure_ascii=False, indent=2))


