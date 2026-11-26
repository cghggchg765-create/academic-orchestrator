"""MM state_utils —— 独立审阅与返修命令（node-review/auto-check/review-loop/repair-check）（由 state_utils.py 拆分而来，勿手改结构；逻辑见各模块）。"""
from state_defs import *  # noqa: F401,F403
from state_scaffold import *  # noqa: F401,F403
from state_audit import *  # noqa: F401,F403

def cmd_node_review(args):
    root = os.path.abspath(args.dir)
    require_node(args.node)
    state = load_state(root)
    node = args.node
    info = NODES[node]
    require_independent_reviewer(node, args.agent)
    require_review_skills(node, args.skills, agent=args.agent)
    # 防审阅偷懒：FAIL/BLOCKED 必须附证据路径（evidence）
    if args.result in {"FAIL", "BLOCKED"} and not (args.evidence or "").strip():
        sys.exit(f"[state_utils] {args.result} 审阅必须提供 --evidence（证据路径，防走过场）")
    # 核心节点 MCP 必调（N1/N3/N4/N5/N7）：PASS 审阅前校验检索留痕，禁止纯内生输出
    if args.result == "PASS":
        require_mcp_search_evidence(root, node, round_no=None,
                                    allow_flag=getattr(args, "allow_missing_mcp", False))
        # N2 数据血缘强制（2.0.0）：D1 放行前必须能交叉检验处理内容/过程/结果
        require_data_lineage(root, node,
                             allow_flag=getattr(args, "allow_missing_lineage", False))
    skills = ",".join(s.strip() for s in args.skills.split(","))
    summary = args.summary or ""
    evidence = args.evidence or "-"
    append_table_row(node_homepage(root, node), "审阅记录",
                     f"| {now_iso()} | {args.agent} | {skills} | {args.result} | {summary} | 证据: {evidence} |")
    # 门禁路由（2.0.0）：主审阅者写 REVIEW_GATE 指定的主门禁；
    # secondary 审阅者（如 mm-figure-table-benchmarker）写它自己的专项门禁，
    # 不得覆盖主门禁——否则「对标通过」会被误当成「格式规范通过」。
    secondaries = NODES[node].get("secondary_reviewers") or []
    if args.agent in secondaries and args.agent != NODES[node].get("reviewer"):
        gate_id = SECONDARY_REVIEWER_GATE.get(args.agent)
    else:
        gate_id = REVIEW_GATE.get(node)
    if gate_id:
        gate = state["gates"].setdefault(gate_id, {"status": "pending"})
        if args.result == "BLOCKED":
            gate.update({"status": "BLOCKED",
                         "agent": args.agent, "timestamp": now_iso(),
                         "result": f"BLOCKED: {summary}"[:200]})
        else:
            gate.update({"status": "PASS" if args.result == "PASS" else "FAIL",
                         "agent": args.agent, "timestamp": now_iso(),
                         "result": f"{args.agent} 审阅{'通过' if args.result == 'PASS' else '未通过'}: {summary}"[:200]})
    save_state(root, state)
    update_homepage_meta(node_homepage(root, node), state["nodes"][node].get("status", "pending"))
    rewrite_homepage_gates(node_homepage(root, node), gate_rows_for(state, node))
    refresh_dashboard(root)
    print(f"[state_utils] node {node} 审阅记录已落盘（{args.agent} -> {args.result}，门禁 {gate_id}）")


def cmd_auto_check(args):
    """自动核查委托（H 门禁）：由配对核查 Agent 自动核验并生成核查报告，流程不挂起，待人工追认。"""
    root = os.path.abspath(args.dir)
    require_node(args.node)
    state = load_state(root)
    node = args.node
    gate = args.gate
    if gate not in {"H1", "H2", "H3"}:
        sys.exit(f"[state_utils] --gate 必须是 H1/H2/H3，实际 {gate}")
    # 核查 Agent 必须是该节点配对审阅 Agent（自动核查 = 独立 Agent 受托执行）
    require_independent_reviewer(node, args.agent)
    require_review_skills(node, args.skills, agent=args.agent)
    summary = args.summary or "自动核查通过"
    report_path = args.report or ""
    if report_path and not os.path.isfile(os.path.join(root, report_path)):
        sys.exit(f"[state_utils] 核查报告文件不存在: {report_path}")

    skills = ",".join(s.strip() for s in args.skills.split(","))
    append_table_row(node_homepage(root, node), "审阅记录",
                     f"| {now_iso()} | {args.agent}（自动核查） | {skills} | AUTO_PASS | {summary} |")
    rel = save_round_report(root, node, args.round, "verification", {
        "agent": args.agent, "node": node, "round": args.round, "timestamp": now_iso(),
        "gate": gate, "result": "AUTO_PASS", "summary": summary, "report_path": report_path or None,
    })
    gate_obj = state["gates"].setdefault(gate, {"status": "pending"})
    gate_obj.update({"status": "auto_passed", "agent": args.agent, "timestamp": now_iso(),
                     "result": f"自动核查通过（{args.agent}）: {summary}"[:200],
                     "verification_report": rel, "confirmed": False})
    # 人工在环记录：不挂起流程，仅登记待追认
    checkpoint = os.path.join(root, STATE_DIR, "human_checkpoint.md")
    if os.path.exists(checkpoint):
        with open(checkpoint, "r", encoding="utf-8") as f:
            text = f.read()
        save_text_atomic(checkpoint, text.rstrip("\n") + f"\n- [{now_iso()}] {gate} 自动核查通过（{args.agent}）：{summary}；待人工追认（h-confirm）。\n")
    save_state(root, state)
    update_homepage_meta(node_homepage(root, node), state["nodes"][node].get("status", "pending"))
    rewrite_homepage_gates(node_homepage(root, node), gate_rows_for(state, node))
    refresh_dashboard(root)
    print(f"[state_utils] auto-check: {node} {gate} -> auto_passed（核查报告 {rel}，待人工追认）")


def cmd_h_confirm(args):
    """人工追认 H 门禁（auto_passed -> confirmed）；也可对 pending 直接确认。"""
    root = os.path.abspath(args.dir)
    state = load_state(root)
    gate = args.gate
    if gate not in {"H1", "H2", "H3"}:
        sys.exit(f"[state_utils] --gate 必须是 H1/H2/H3，实际 {gate}")
    gate_obj = state["gates"].setdefault(gate, {"status": "pending"})
    gate_obj.update({"status": "confirmed", "timestamp": now_iso(),
                     "result": f"人工确认（{args.note or '用户确认'}）"[:200], "confirmed": True})
    save_state(root, state)
    refresh_dashboard(root)
    print(f"[state_utils] h-confirm: {gate} -> confirmed")


def cmd_review_loop(args):
    """审阅-修改-再审阅循环（通用协议序列）：执行产出 → 独立审阅 → PASS 完成 / FAIL → 修改 Agent 按 feedback
    修改（必须加载本节点 skill）→ 再审阅（≤2 次，防空返修）→ 通过/上限。适用单项、阶段与整体系列任务。"""
    root = os.path.abspath(args.dir)
    require_node(args.node)
    node = args.node
    if node == "N0":
        sys.exit("[state_utils] N0 无审阅环节")
    state = load_state(root)
    info = NODES[node]
    executor = info.get("executor") or "-"
    reviewer = info.get("reviewer") or "-"
    review_mode = info.get("review_mode") or "node-review"
    skills = ",".join(info.get("skills", []))
    artifacts = [p.strip() for p in info.get("artifact", "").split(",") if p.strip()]
    max_attempts = 2  # 防死循环：返修硬上限

    # 当前产物快照（防空返修：返修必须产生产物变化）
    def snapshot():
        return {p: sha256_of(os.path.join(root, p)) if os.path.isfile(os.path.join(root, p)) else None for p in artifacts}

    base = snapshot()
    steps = []
    for attempt in range(max_attempts + 1):
        label = "初审" if attempt == 0 else f"第 {attempt} 次复审"
        cmd = f"python state/state_utils.py node-review {node} --agent {reviewer} --result <PASS|FAIL|BLOCKED> --skills {skills} --evidence <证据路径,逗号分隔> --summary <结论>"
        if review_mode in {"code-score", "tune-check"}:
            cmd = (f"python state/state_utils.py round-score {node} --round <n> --total <总分> --dims '<五维JSON>' "
                   f"--judge {reviewer} --skills-read {skills} --evidence <证据路径>")
        steps.append({"attempt": attempt, "kind": "review", "label": label,
                      "reviewer": reviewer, "cmd": cmd,
                      "description": f"① 调用独立审阅 Agent {reviewer} 审阅（先读配对 skill 并声明；FAIL/BLOCKED 必须附 evidence）"})
        if attempt < max_attempts:
            steps.append({"attempt": attempt, "kind": "modify", "label": f"第 {attempt + 1} 次修改",
                          "modify_agent": executor, "modify_skills": info.get("skills", []),
                          "cmd": f"python state/state_utils.py node-repair-check {node} --attempt {attempt + 1} --dir .",
                          "description": f"② 修改 Agent {executor} 按审阅 feedback 修改/润色（必须先加载 skill: {skills}；"
                                         f"必须修改产物，空返修打回）→ 对比产物哈希变化：{', '.join(artifacts)}"})
            steps.append({"attempt": attempt, "kind": "re_review", "label": label,
                          "description": f"③ 返回第 {attempt + 1} 步再审阅（同审阅 Agent，比对上轮 feedback 是否已处理）"})
    steps.append({"kind": "escalate", "cmd": None,
                  "description": f"达上限（{max_attempts} 次修改）仍未通过 → 写 BLOCKED/ESCALATE + 人工介入（防死循环）"})
    print(json.dumps({
        "node": node, "executor": executor, "reviewer": reviewer, "review_mode": review_mode,
        "max_modify_attempts": max_attempts, "required_skills": info.get("skills", []),
        "protocol": "审阅 → 修改（加载本节点 skill）→ 再审阅，往复至 PASS；未审阅不得标完成（audit 检测）",
        "artifact_snapshot": base, "steps": steps,
        "anti_laziness": ["审阅必须附 evidence（防走过场）", "修改必须产生产物哈希变化（空修改打回）", "修改必须加载本节点 skill"],
        "dead_loop_guard": f"修改硬上限 {max_attempts} 次；达上限转 BLOCKED/ESCALATE",
    }, ensure_ascii=False, indent=2))


def cmd_node_repair_check(args):
    """返修哈希对比（防空返修）：对比节点产物快照，无变化视为空返修并记录。"""
    root = os.path.abspath(args.dir)
    require_node(args.node)
    node = args.node
    artifacts = [p.strip() for p in NODES[node].get("artifact", "").split(",") if p.strip()]
    before = {p: (sha256_of(os.path.join(root, p)) if os.path.isfile(os.path.join(root, p)) else None) for p in artifacts}
    snap = os.path.join(root, STATE_DIR, "nodes", NODES[node]["dir"], "repair_snapshot.json")
    if os.path.exists(snap):
        prev = load_json(snap) or {}
        changed = [p for p in artifacts if prev.get(p) != before.get(p)]
        empty = not changed
        save_json_atomic(snap, before)
        status = "EMPTY_REPAIR" if empty else "CHANGED"
        print(json.dumps({"node": node, "attempt": args.attempt, "status": status,
                          "changed": changed, "unchanged": [p for p in artifacts if p not in changed],
                          "note": "空返修打回并计入返修次数" if empty else "返修有效"}, ensure_ascii=False, indent=2))
    else:
        save_json_atomic(snap, before)
        print(json.dumps({"node": node, "attempt": args.attempt, "status": "SNAPSHOT",
                          "note": "已记录返修前产物哈希快照"}, ensure_ascii=False, indent=2))


