"""MM state_utils —— 独立审阅与返修命令（node-review/auto-check/review-loop/repair-check）（由 state_utils.py 拆分而来，勿手改结构；逻辑见各模块）。"""
from state_defs import *  # noqa: F401,F403
from state_scaffold import *  # noqa: F401,F403
from state_audit import *  # noqa: F401,F403

def require_correction_closure(root, node, gate_id):
    """纠正留痕闭环校验（CORRECTION_UNACKED）——A3/B1 门禁的真实执行者。

    文档承诺（skills/academic-orchestration/SKILL.md「D. 纠偏留痕」+ gates-registry A3/B1 判据）：
    某节点发生过纠正，则必须存在对应回执，否则 A3 不得 PASS。此前这条门禁只有文档、没有代码，
    这里补上机器校验，并做四层防伪造：

      ① 逐条配对：按 correction_id 匹配回执，一条回执不能抵多条纠正；
      ② 同一 agent：回执的 agent_id 必须等于纠正记录的 agent_id（主 Agent 代签无效）；
      ③ 时间不可倒置：回执时间不得早于纠正时间；
      ④ 账本不可篡改：corrections/acks 两份 JSONL 的哈希链必须连续，断裂即判
         CORRECTION_LEDGER_TAMPERED（防止事后删掉"未回执"的纠正记录来骗门禁）。

    A3（N8 终审）查全项目；B1（图表对标）只查当前节点——B1 在 N6/N7/N8 都可触发，
    不能拿别的节点的回执顶替。
    """
    from state_events import summarize_corrections, unacked_corrections

    scope_node = None if gate_id == "A3" else node
    summary = summarize_corrections(root, node=scope_node)
    if not summary["chain"]["intact"]:
        chain = summary["chain"]
        sys.exit(
            f"[state_utils] 🔴 拒绝 {gate_id} PASS：纠正留痕账本哈希链断裂"
            f"（corrections={chain['corrections']['broken_at']}, "
            f"acks={chain['acks']['broken_at']}）——判 CORRECTION_LEDGER_TAMPERED。\n"
            f"  说明纠正记录或回执被事后改写/删除；门禁不能建立在被篡改的留痕上。\n"
            f"  处置：恢复被改动的记录，或由主 Agent 重新登记纠正并重收回执。"
        )
    unacked = unacked_corrections(root, node=scope_node)
    if not unacked:
        scope = "全项目" if scope_node is None else f"节点 {scope_node}"
        if summary["total"]:
            print(f"[state_utils] 纠正留痕闭环通过（{scope}：{summary['total']} 条纠正均已回执）")
        return
    detail = []
    for corr in unacked[:10]:
        detail.append(
            f"  - {corr.get('correction_id')} node={corr.get('node')} "
            f"agent={corr.get('agent_id')} round={corr.get('round') or '-'} "
            f"type={corr.get('type')} delivery={corr.get('delivery')}\n"
            f"      要求: {str(corr.get('requirement') or '')[:100]}"
        )
    scope = "全项目" if scope_node is None else f"节点 {scope_node}"
    sys.exit(
        f"[state_utils] 🔴 拒绝 {gate_id} PASS：CORRECTION_UNACKED（{scope} 有 "
        f"{len(unacked)} 条纠正未收到对应 Agent 的回执）。\n"
        + "\n".join(detail)
        + ("\n  …" if len(unacked) > 10 else "")
        + "\n  门禁判据：纠正留痕闭环（gates-registry " + gate_id + "）——发生过纠正就必须有同一 "
          "agent_id 的回执，否则不能判定「纠正已生效」。\n"
          "  收口方式：子 Agent 本人执行\n"
          "    python state/state_utils.py correction-ack <correction_id> --agent <agent_id> "
          "--note \"<如何落实>\"\n"
          "  主 Agent 代签无效（agent_id 必须与纠正记录一致）。"
    )


BENCHMARK_DIMS = ("data_columns", "statistics", "units", "comparability",
                  "grouping", "chart_fit", "academic_form")
BENCHMARK_VERDICTS = {"COMPLETE", "GAP_MINOR", "GAP_MAJOR", "BLOCKED"}


def _validate_benchmark_manually(data):
    """jsonschema 不可用时的等效手检（B1）。

    只覆盖"能被绕过"的关键点：entries 结构、七维齐全且每维有 state/evidence、
    verdict 枚举合法。宁可比 schema 松，也不能比它松到让空壳矩阵过关。
    """
    entries = data.get("entries") or []
    problems = []
    for idx, entry in enumerate(entries):
        entry = entry or {}
        tag = entry.get("artifact_id") or f"entries[{idx}]"
        for key in ("artifact_id", "artifact_kind", "supported_claim", "verdict"):
            if not entry.get(key):
                problems.append(f"{tag} 缺 {key}")
        if entry.get("verdict") and entry["verdict"] not in BENCHMARK_VERDICTS:
            problems.append(f"{tag} verdict={entry['verdict']} 非法")
        dims = entry.get("dimensions") or {}
        for dim in BENCHMARK_DIMS:
            node_dim = dims.get(dim)
            if not isinstance(node_dim, dict):
                problems.append(f"{tag} 缺维度 {dim}")
            elif not node_dim.get("state"):
                problems.append(f"{tag}.{dim} 缺 state")
            elif not node_dim.get("evidence"):
                problems.append(f"{tag}.{dim} 缺 evidence（无证据的判定视为未判定）")
        if not (entry.get("benchmarked") or []):
            problems.append(f"{tag} 缺 benchmarked（至少要有一篇同行论文）")
    if problems:
        sys.exit("[state_utils] 拒绝 B1 PASS：对标矩阵结构不完整（jsonschema 不可用，已做等效手检）：\n  - "
                 + "\n  - ".join(problems[:10])
                 + ("\n  …" if len(problems) > 10 else "")
                 + "\n  完整格式见 skills/figure-table-benchmark/references/benchmark-matrix.schema.json")


def require_b1_evidence(root, node, agent, evidence):
    """B1 门禁专项校验（P1-2）。

    原实现只要求声明的 skills，不检查任何对标产物 → 无反差矩阵也能 PASS。
    现在要求：
      1. state/reports/figure-table-benchmark/ 下有矩阵文件；
      2. 该文件能解析，且 entries 非空、每条有 verdict；
      3. 无 GAP_MAJOR/BLOCKED（有则 FAIL，不放行）。
    """
    bdir = os.path.join(root, "state", "reports", "figure-table-benchmark")
    if not os.path.isdir(bdir):
        sys.exit(
            "[state_utils] 拒绝 B1 PASS：缺少对标矩阵目录 state/reports/figure-table-benchmark/。\n"
            "  B1 要求先检索 ≥3 篇同领域论文并产出实测规格矩阵，格式见\n"
            "    skills/figure-table-benchmark/references/benchmark-matrix.schema.json\n"
            "  再执行 node-review ... --result PASS --evidence <矩阵路径>"
        )
    candidates = []
    if evidence:
        p = evidence if os.path.isabs(evidence) else os.path.join(root, evidence)
        if os.path.isfile(p):
            candidates.append(p)
    if not candidates:
        for f in sorted(os.listdir(bdir)):
            if f.endswith(".json"):
                candidates.append(os.path.join(bdir, f))
    if not candidates:
        sys.exit("[state_utils] 拒绝 B1 PASS：对标矩阵目录下没有任何 .json 矩阵文件。")

    latest = max(candidates, key=os.path.getmtime)
    try:
        data = json.loads(open(latest, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"[state_utils] 拒绝 B1 PASS：对标矩阵无法解析（{latest}）：{exc}")

    entries = data.get("entries") or []
    if not entries:
        sys.exit(f"[state_utils] 拒绝 B1 PASS：矩阵 {os.path.basename(latest)} 的 entries 为空。")
    # P0-6：矩阵节点必须与本节点一致（N6 的 B1 不能顶替 N7/N8 的对标要求）
    m_node = data.get("node")
    if m_node and m_node != node:
        sys.exit(f"[state_utils] 拒绝 B1 PASS：矩阵 node={m_node} 与当前节点 {node} 不符。\n"
                 f"  N6/N7/N8 各自需要针对本节点产物的对标矩阵。")
    # P0-6：用 benchmark-matrix.schema.json 做结构校验（原先只看 verdict 与篇数）
    schema_path = None
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for cand in (os.path.join(here, "skills", "figure-table-benchmark", "references",
                              "benchmark-matrix.schema.json"),):
        if os.path.isfile(cand):
            schema_path = cand
            break
    if schema_path:
        try:
            import jsonschema
            jsonschema.Draft202012Validator(
                json.loads(open(schema_path, encoding="utf-8").read())).validate(data)
        except ImportError:
            # 无 jsonschema 时不能静默放行：下方逐条手检只覆盖 verdict/benchmarked，
            # 不查七维 dimensions——一份"verdict=COMPLETE 但七维全空"的矩阵会蒙混过关。
            # 这里补做与 schema 等效的关键字段检查。
            _validate_benchmark_manually(data)
        except jsonschema.ValidationError as exc:
            loc = "/".join(str(p) for p in exc.absolute_path) or "(root)"
            sys.exit(f"[state_utils] 拒绝 B1 PASS：矩阵结构不符（{loc}）：{exc.message[:160]}")
        except (OSError, json.JSONDecodeError):
            pass
    bad = []
    for e in entries:
        e = e or {}
        verdict = e.get("verdict")
        if verdict in {"GAP_MAJOR", "BLOCKED"}:
            bad.append(f"{e.get('artifact_id', '?')}={verdict}")
        elif not verdict:
            bad.append(f"{e.get('artifact_id', '?')}=<缺 verdict>")
        # 每篇对标必须带 locator 与 channel（否则无法复核，等于编造）
        for i, b in enumerate(e.get("benchmarked") or []):
            b = b or {}
            missing = [k for k in ("paper_id", "year", "locator", "channel") if not b.get(k)]
            if missing:
                bad.append(f"{e.get('artifact_id','?')}.benchmarked[{i}] 缺 {missing}")
    if bad:
        sys.exit("[state_utils] 拒绝 B1 PASS：存在未达标或不可核对的条目："
                 + ", ".join(bad[:8])
                 + ("…" if len(bad) > 8 else "")
                 + "\n  每条对标必须给 paper_id/year/locator/channel，否则视为编造。")
    # 对标论文数（可选字段）：不足 3 篇不给 PASS
    for e in entries:
        n = len((e or {}).get("benchmarked") or [])
        if n < 3:
            sys.exit(f"[state_utils] 拒绝 B1 PASS：条目 {e.get('artifact_id','?')} 只对标了 {n} 篇，"
                     f"要求 ≥3 篇同领域论文。")


def cmd_node_review(args):
    root = os.path.abspath(args.dir)
    require_node(args.node)
    state = load_state(root)
    node = args.node
    info = NODES[node]
    require_independent_reviewer(node, args.agent)
    require_review_skills(node, args.skills, agent=args.agent, project=root)
    # 防审阅偷懒：FAIL/BLOCKED 必须附证据路径（evidence）
    # 核心节点 MCP 必调（N1/N3/N4/N5/N7）：PASS 审阅前校验检索留痕，禁止纯内生输出
    if args.result == "PASS":
        require_mcp_search_evidence(root, node, round_no=None,
                                    allow_flag=getattr(args, "allow_missing_mcp", False))
        # N2 数据血缘强制（2.0.0）：D1 放行前必须能交叉检验处理内容/过程/结果
        require_data_lineage(root, node,
                             allow_flag=getattr(args, "allow_missing_lineage", False))
    # P0-5：PASS 也必须附**真实存在**的证据。原先只有 FAIL/BLOCKED 要求 --evidence，
    # 于是 `--evidence /nonexistent/FAKE.md` 乃至完全省略都能通过门禁，审计无法区分真伪。
    # 顺序：先做业务校验（MCP/血缘），最后校验证据文件存在——否则业务错误会被证据错误掩盖。
    if args.result in {"FAIL", "BLOCKED", "PASS"}:
        ev = (args.evidence or "").strip()
        if not ev:
            sys.exit(f"[state_utils] {args.result} 审阅必须提供 --evidence（证据路径）")
        ev_path = ev if os.path.isabs(ev) else os.path.join(root, ev)
        if not os.path.exists(ev_path):
            sys.exit(f"[state_utils] 证据文件不存在: {ev}\n"
                     f"  审阅结论必须绑定可核对的实际产物（文件/目录），不接受路径占位。")
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
    # 2.0.0 纠正留痕闭环：A3 终审与 B1 对标 PASS 前，该节点（A3 为全项目）的每条纠正必须有回执，
    # 否则判 CORRECTION_UNACKED。此前该门禁只有文档承诺，没有任何机器校验（纸面门禁）。
    if gate_id in {"A3", "B1"} and args.result == "PASS":
        require_correction_closure(root, node, gate_id)
    # P1-2：B1 的 PASS 必须有实测对标矩阵支撑，不能只靠声明的 skills。
    if gate_id == "B1" and args.result == "PASS":
        require_b1_evidence(root, node, args.agent, args.evidence or "")
    if gate_id:
        gate = state["gates"].setdefault(gate_id, {"status": "pending"})
        prev_status = gate.get("status", "pending")
        if args.result == "BLOCKED":
            gate.update({"status": "BLOCKED",
                         "agent": args.agent, "timestamp": now_iso(),
                         "result": f"BLOCKED: {summary}"[:200]})
        else:
            gate.update({"status": "PASS" if args.result == "PASS" else "FAIL",
                         "agent": args.agent, "timestamp": now_iso(),
                         "result": f"{args.agent} 审阅{'通过' if args.result == 'PASS' else '未通过'}: {summary}"[:200]})
        # 门禁事件流（append-only + 哈希链）：留下"谁、何时、凭什么"的可审计轨迹
        try:
            from state_events import record_gate_change
            record_gate_change(root, gate_id, prev_status, gate["status"], args.agent,
                               source_cmd="node-review", evidence=args.evidence or None,
                               exemption=("lineage" if getattr(args, "allow_missing_lineage", False) else None),
                               note=summary[:120])
        except Exception as exc:  # 事件流失败不阻断主流程，但要在 stderr 提示
            print(f"[state_utils] ⚠ 门禁事件记录失败: {exc}", file=sys.stderr)
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
    require_review_skills(node, args.skills, agent=args.agent, project=root)
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


