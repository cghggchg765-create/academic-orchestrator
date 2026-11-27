"""MM state_utils —— 迭代轮次命令（round-start/score/decide、merge、版本记录）（由 state_utils.py 拆分而来，勿手改结构；逻辑见各模块）。"""
from state_defs import *  # noqa: F401,F403
from state_scaffold import *  # noqa: F401,F403
from state_audit import *  # noqa: F401,F403
from state_scopes import *  # noqa: F401,F403


def collect_round_cards(root, node, round_no):
    """采集某节点某轮沉淀的知识卡片文件名（命名约定 `{节点}_r{轮}_{slug}.md`，落 state/reports/mcp-cards/）。

    round-score 时写入 rounds[n].knowledge_cards，使"每轮检索→卡片沉淀"可精确追踪；
    N8 终检可据此核对"每轮有新检索、有卡片沉淀"（禁止纯内生）。"""
    cards = []
    d = os.path.join(root, STATE_DIR, "reports", "mcp-cards")
    if os.path.isdir(d):
        prefix = f"{node}_r{round_no}_"
        cards = sorted(f for f in os.listdir(d)
                       if f.startswith(prefix) and f.lower().endswith(".md"))
    return cards


def _round_scope_id(args):
    """Normalize optional scope id while leaving omitted calls legacy-compatible."""
    value = getattr(args, "scope_id", None)
    if not value:
        return None
    try:
        return safe_scope_id(value)
    except (ScopeError, ValueError) as exc:
        sys.exit(f"[state_utils] 非法 scope-id: {exc}")


def _find_round(state, node, round_no, scope_id=None):
    matches = [r for r in state["rounds"]
               if r.get("node") == node and r.get("round") == round_no
               and (r.get("scope_id") == scope_id if scope_id else not r.get("scope_id"))]
    return matches[0] if matches else None


def _scope_round_phase(root, node, round_no, scope_id, phase, status="completed"):
    if not scope_id:
        return
    try:
        update_scope_phase(root, node, round_no, scope_id, phase, status)
    except ScopeError as exc:
        sys.exit(f"[state_utils] 作用域 {scope_id} 阶段更新失败: {exc}")


def _deadline_passed(deadline):
    """判断 budget.deadline 是否已过。返回 (passed, note)。

    此前直接 `now_iso() > deadline` 做字符串比较，只有当 deadline 恰好写成
    同格式 ISO 串时才对：
      deadline="2026-11-26"          → "2026-11-26T15:04Z" > "2026-11-26" 为 True，
                                       即当天一开始就被当成"已截止"（差一天）
      deadline="2026-11-26T23:59:00Z" → 正常
      deadline="2026-11-26 23:59"     → 空格 < "T"，同一天内恒为 True
    配置是人手写的，格式无法假定。这里统一解析成 UTC datetime 再比；
    解析失败则返回 (False, 提示)，不静默当作"没有截止"。
    """
    text = str(deadline or "").strip()
    if not text:
        return False, ""
    now = datetime.now(timezone.utc)
    # 只给日期 → 视为当天 23:59:59 UTC 截止（给用户留满当天）
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            due = datetime.strptime(text, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc)
        else:
            normalized = text.replace(" ", "T").replace("Z", "+00:00")
            due = datetime.fromisoformat(normalized)
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            else:
                due = due.astimezone(timezone.utc)
    except ValueError:
        return False, (f"budget.deadline={text!r} 不是可解析的时间"
                       f"（支持 YYYY-MM-DD 或 ISO-8601），本次按未设截止处理")
    return now > due, ""


def missing_dimensions(node, dims):
    """返回该环尚未给分的维度名集合。

    历史契约允许只给部分维度（既有测试以单维度调用 round-score 验证门禁接线），
    因此这里不拒绝落盘，而是把缺失维度暴露出来：写入 score.dimensions_partial
    并在 stderr 告警，避免"少交维度 = 逃避该维扣分与硬上限"完全无声。
    """
    code_dims = {"correctness", "efficiency", "readability", "robustness", "innovation"}
    paper_dims = {"假设合理性", "建模创造性", "结果正确性", "表述清晰性", "格式规范性"}
    allowed_dims = code_dims if PROFILE_OF[node] == "code" else paper_dims
    return allowed_dims - set(dims)


def cmd_round_start(args):
    root = os.path.abspath(args.dir)
    require_node(args.node, allowed=set(PROFILE_OF))
    state = load_state(root)
    node = args.node
    scope_id = getattr(args, "scope_id", None)
    if scope_id:
        try:
            scope_id = safe_scope_id(scope_id)
        except (ScopeError, ValueError) as exc:
            sys.exit(f"[state_utils] 非法 scope-id: {exc}")
    verify_problem_lock(root)
    # 2.0.0（P0-2）：开轮前必须满足与 node-start 相同的前置——
    # 上游 completed + 上游全部门禁 PASS + 上游产物未漂移。否则可零工作量开轮并完成。
    # 注意：这里不要求本节点已 node-start（开轮可以先于/后于节点开工），
    # "必须 start 过"由 round-decide 的完成守卫检查。
    # --skip-prereq 仅供单测构造场景使用（生产禁用，会在 rounds 留痕）。
    from state_guard import check_upstream
    if getattr(args, "skip_prereq", False):
        state.setdefault("meta", {}).setdefault("prereq_skips", []).append(
            {"at": now_iso(), "node": node, "reason": "round-start --skip-prereq（测试/迁移）"})
    else:
        up_errs = check_upstream(root, node, state)
        if up_errs:
            sys.exit(
                f"[state_utils] 拒绝 round-start {node}（{len(up_errs)} 项前置不满足）：\n  - "
                + "\n  - ".join(up_errs[:8])
            )
    if any(r.get("node") == node and r.get("status") == "in_progress"
           and (r.get("scope_id") == scope_id if scope_id else not r.get("scope_id")) for r in state["rounds"]):
        suffix = f" scope={scope_id}" if scope_id else ""
        sys.exit(f"[state_utils] 节点 {node}{suffix} 已有未决策（in_progress）的轮次，请先 round-score + round-decide 再开新轮")
    rounds = [r for r in state["rounds"] if r.get("node") == node
              and (r.get("scope_id") == scope_id if scope_id else not r.get("scope_id"))]
    n = max((r["round"] for r in rounds), default=0) + 1
    branch = args.branch or f"round{n}_{node.lower()}" + (f"_{scope_id}" if scope_id else "")
    if args.git:
        require_git(root)
        r = git(["checkout", "-b", branch], cwd=root)
        if r.returncode != 0:
            sys.exit(f"[state_utils] 分支创建失败（{branch} 可能已存在）: {r.stderr.strip()}")
    round_record = {
        "round": n, "node": node, "branch": branch, "goal": args.goal or state["nodes"][node].get("goal", ""),
        "started": now_iso(), "status": "in_progress", "case_refs": [], "agent_claims": [],
        "artifacts": [], "run": {}, "commits": [], "score": None, "decision": None,
    }
    if scope_id:
        round_record.update({"scope_id": scope_id, "scope_key": f"{node}:r{n}:{scope_id}",
                             "scope_kind": "scope", "attempt": 1,
                             "run_id": f"round-{node.lower()}-{n}-{scope_id}"})
    state["rounds"].append(round_record)
    state["meta"]["current_round"] = n
    state["nodes"][node]["status"] = "in_progress"
    state["stages"][NODES[node]["stage"]]["status"] = "in_progress"
    save_state(root, state)
    update_homepage_meta(node_homepage(root, node), "in_progress")
    refresh_dashboard(root)
    print(f"[state_utils] round-start: node={node} round={n} branch={branch}")


def git_commit_state(root, message, round_no=None, agent=None, score=None, dims=None, node=None, gate=None):
    body = [message, ""]
    if round_no:
        body.append(f"Round: {round_no}")
    if node:
        body.append(f"Stage: {node}")
    if agent:
        body.append(f"Agent: {agent}")
    if gate:
        body.append(f"Gate: {gate}")
    if score is not None:
        s = {"total": score}
        if dims:
            s["dimensions"] = dims
        body.append(f"Score: {json.dumps(s, ensure_ascii=False)}")
    body.append(f"State-Sha: {sha256_of(os.path.join(root, STATE_FILE))[:8]}")
    git(["add", STATE_DIR], cwd=root)
    git(["add", os.path.join("LogRecord", "version-update.md")], cwd=root)
    r = git(["commit", "-m", "\n".join(body)], cwd=root)
    return r


def cmd_round_score(args):
    root = os.path.abspath(args.dir)
    require_node(args.node, allowed=set(PROFILE_OF))
    state = load_state(root)
    node = args.node
    scope_id = _round_scope_id(args)
    require_independent_reviewer(node, args.judge)
    # P1-6：轮次评分只允许节点主审阅者（REVIEW_GATE 对应的那个）提交整体分，
    # 不允许 secondary reviewer（如图表对标者）给论文/代码轮次打整体分——
    # 否则可跳过 mm-latex-writing / mm-self-review 的评审口径。
    #
    # 例外（维度分工）：DIMENSION_SPLIT 声明的第二审阅者可提交**它负责的那几个维度**，
    # 但不能给 --total（整体分仍由主审阅者定）。这样"readability/innovation 由独立方评"
    # 才真正落地，又不会让第二审阅者接管整体判定。
    main_reviewer = NODES[node].get("reviewer")
    split = DIMENSION_SPLIT.get(node) or {}
    split_agent = split.get("agent")
    split_dims = set(split.get("dimensions") or [])
    is_split_review = bool(split_agent) and args.judge == split_agent and split_agent != main_reviewer
    if main_reviewer and args.judge != main_reviewer and not is_split_review:
        hint = ""
        if split_agent:
            hint = (f"\n  若你是 {split_agent}，可只提交维度分工里属于你的维度："
                    f"{sorted(split_dims)}（不传 --total）。")
        sys.exit(
            f"[state_utils] 拒绝：{node} 的轮次评分 judge 必须是主审阅者 {main_reviewer}，"
            f"实际为 {args.judge}。\n"
            f"  secondary reviewer（如 mm-figure-table-benchmarker）只通过 node-review "
            f"登记其专项门禁（B1），不参与轮次五维评分。" + hint
        )
    # 传 agent：分工审阅者只需读自己维度的规范，不能按主审阅者的清单要求它
    require_review_skills(node, args.skills_read, agent=args.judge, project=root)

    try:
        dims = json.loads(args.dims)
    except Exception as e:
        sys.exit(f"[state_utils] --dims 必须为合法 JSON: {e}")
    target_round = _find_round(state, node, args.round, scope_id)
    if target_round is None:
        suffix = f" scope={scope_id}" if scope_id else ""
        sys.exit(f"[state_utils] 未找到 node={node} round={args.round}{suffix}。\n"
                 f"  请先开轮: python state/state_utils.py round-start {node}"
                 f"{' --scope-id ' + scope_id if scope_id else ''} --dir .\n"
                 f"  已开轮次可查: python state/state_utils.py dump --dir .")
    if target_round.get("status") != "in_progress":
        sys.exit(
            f"[state_utils] 轮次 {node}/round{args.round} 不可评分，当前状态: "
            f"{target_round.get('status')}\n"
            f"  评分只对 in_progress 轮次有效。继续本轮请先开新轮：\n"
            f"    python state/state_utils.py round-start {node} --dir .\n"
            f"  查看已有轮次：python state/state_utils.py dump --dir ."
        )
    if target_round.get("score") is not None:
        sys.exit(f"[state_utils] 轮次 {node}/round{args.round} 已评分，拒绝重复写入。\n"
                 f"  评分是 append-only 审计留痕；若确需重评，请开新轮：\n"
                 f"    python state/state_utils.py round-start {node} --dir .")
    # 核心节点 MCP 必调：迭代每轮必须重新检索（禁止纯内生输出）——本轮无检索留痕则拒绝评分
    require_mcp_search_evidence(root, node, round_no=args.round,
                                allow_flag=getattr(args, "allow_missing_mcp", False))
    # 维度分工场景：第二审阅者只提交自己负责的维度，不传 --total。
    # 校验：他提交的维度必须都在自己分工范围内，不能越界评别人的维度。
    if is_split_review:
        out_of_scope = set(dims) - split_dims
        if out_of_scope:
            sys.exit(
                f"[state_utils] 拒绝：{args.judge} 在 {node} 只负责维度 {sorted(split_dims)}，"
                f"不能评 {sorted(out_of_scope)}。\n"
                f"  分工理由：{split.get('rationale', '')}\n"
                f"  其余维度由主审阅者 {main_reviewer} 在整体评分中给出。"
            )
        # 记录到 round 的 dimension_contributions，供主审阅者汇总
        contrib = target_round.setdefault("dimension_contributions", {})
        contrib[args.judge] = {
            "dimensions": dims,
            "skills_read": [s.strip() for s in args.skills_read.split(",") if s.strip()],
            "evidence": [s.strip() for s in (args.evidence or "").split(",") if s.strip()],
            "timestamp": now_iso(),
        }
        save_state(root, state, bump=False)
        print(json.dumps({"recorded": True, "node": node, "round": args.round,
                          "judge": args.judge, "dimensions": dims,
                          "note": "维度分工分已记录；整体分由主审阅者汇总后提交"},
                         ensure_ascii=False, indent=2))
        return
    if not isinstance(dims, dict) or not dims:
        sys.exit("[state_utils] --dims 必须是非空 JSON 对象")
    if args.total is None:
        sys.exit(
            f"[state_utils] 主审阅者必须提供 --total（0-10 整体分）。\n"
            f"  --total 只在维度分工的第二审阅者提交单项维度时可省略。"
        )
    total = float(args.total)
    if not math.isfinite(total) or not 0 <= total <= 10:
        sys.exit("[state_utils] --total 必须是 0 到 10 之间的有限数")
    for key, value in dims.items():
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 <= float(value) <= 10:
            sys.exit(f"[state_utils] 评分维度 {key} 必须是 0 到 10 之间的有限数")
    # 五维键名合法性校验（防乱写维度/口径漂移）：code 环英文五维，paper 环中文五维
    code_dims = {"correctness", "efficiency", "readability", "robustness", "innovation"}
    paper_dims = {"假设合理性", "建模创造性", "结果正确性", "表述清晰性", "格式规范性"}
    allowed_dims = code_dims if PROFILE_OF[node] == "code" else paper_dims
    unknown_dims = set(dims) - allowed_dims
    if unknown_dims:
        sys.exit(f"[state_utils] 评分维度键名非法: {sorted(unknown_dims)}（{PROFILE_OF[node]} 环允许: {sorted(allowed_dims)}）")
    # 缺维度不拦（历史契约允许部分评分），但必须留痕，避免静默逃避硬上限
    absent_dims = sorted(missing_dimensions(node, dims))
    if absent_dims:
        print(f"[state_utils] ⚠ 评分缺维度 {absent_dims}（{PROFILE_OF[node]} 环）——"
              f"缺的维度不参与硬上限判定，建议补齐五维", file=sys.stderr)
    target_round["score"] = {"total": total, "dimensions": dims, "judge": args.judge,
                             "skills_read": [s.strip() for s in args.skills_read.split(",") if s.strip()],
                             "evidence": [s.strip() for s in args.evidence.split(",") if s.strip()],
                             "timestamp": now_iso(), "notes_sha": None}
    if absent_dims:
        target_round["score"]["dimensions_partial"] = absent_dims
    if scope_id:
        target_round["score"].update({"scope_id": scope_id, "scope_key": target_round.get("scope_key")})
    # 本轮知识卡片引用（命名约定 {node}_r{round}_{slug}.md）：使"每轮检索→卡片沉淀"可追踪，N8 终检核对"迭代有新检索"
    target_round["knowledge_cards"] = collect_round_cards(root, node, args.round)
    profile = state["termination"][PROFILE_OF[node]]
    gate_id = f"S{args.round}-{node}" + (f"-{scope_id}" if scope_id else "")
    target_round["gates_sn"] = gate_id
    gate_status = "PASS" if total >= profile["pass"] else "FAIL"
    gate = state["gates"].setdefault(gate_id, {"status": "pending"})
    gate.update({"status": gate_status, "agent": args.judge, "timestamp": now_iso(),
                 "result": f"total={total} (pass={profile['pass']})", "node": node})
    if scope_id:
        gate["scope_id"] = scope_id
    # 达标自动落盘辅助硬门禁（消除 A1/A2 无落盘路径的断链）：N4 达标 → A1；N7 达标 → A2
    if gate_status == "PASS":
        aux_gate = {"N4": "A1", "N7": "A2"}.get(node)
        if aux_gate:
            aux = state["gates"].setdefault(aux_gate, {"status": "pending"})
            aux.update({"status": "PASS", "agent": args.judge, "timestamp": now_iso(),
                        "result": f"round{args.round} total={total} >= pass {profile['pass']}，自动通过（反模式扫描随评分判定）"})
    upsert_row_by_first_cell(node_homepage(root, node), "迭代记录", args.round,
                             f"| {args.round} | {target_round.get('branch', '-')} | {total} | - | - |")
    save_round_report(root, node, args.round, "review", {
        "agent": args.judge, "node": node, "round": args.round, "timestamp": now_iso(),
        "verdict": gate_status, "total": total, "dimensions": dims,
        "skills_read": target_round["score"]["skills_read"], "evidence": target_round["score"]["evidence"],
        "pass_threshold": profile["pass"], "target_threshold": profile["target"],
        "scope_id": scope_id, "scope_key": target_round.get("scope_key"), "phase": "SCORE",
    }, scope_id=scope_id)
    _scope_round_phase(root, node, args.round, scope_id, "SCORE", "completed")
    save_state(root, state)
    if args.git:
        require_git(root)
        r = git_commit_state(root, f"score: {node} round{args.round} 评分 {total}",
                             round_no=args.round, agent=args.judge, score=total, dims=dims,
                             node=node, gate=f"{gate_id} {gate_status}")
        if r.returncode == 0:
            notes = json.dumps({"round": args.round, "node": node, "total": total,
                                "dimensions": dims, "judge": args.judge}, ensure_ascii=False)
            git(["notes", "--ref=score", "add", "-f", "-m", notes, "HEAD"], cwd=root)
        else:
            print(f"[state_utils] ⚠ git 提交失败: {r.stderr.strip()}")
    rewrite_homepage_gates(node_homepage(root, node), gate_rows_for(state, node))
    refresh_dashboard(root)
    print(f"[state_utils] round-score: node={node} round={args.round} total={total} gate={gate_id} {gate_status}")


def append_version_update(root, row):
    path = os.path.join(root, "LogRecord", "version-update.md")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    save_text_atomic(path, text.rstrip("\n") + "\n" + row.rstrip("\n") + "\n")


def cmd_round_decide(args):
    root = os.path.abspath(args.dir)
    require_node(args.node, allowed=set(PROFILE_OF))
    state = load_state(root)
    node = args.node
    scope_id = _round_scope_id(args)
    target_round = _find_round(state, node, args.round, scope_id)
    if target_round is None:
        suffix = f" scope={scope_id}" if scope_id else ""
        sys.exit(f"[state_utils] 未找到 node={node} round={args.round}{suffix}")
    if target_round.get("decision") is not None:
        sys.exit(f"[state_utils] 轮次 {node}/round{args.round} 已有决策，拒绝重复决策")
    if not target_round.get("score"):
        sys.exit("[state_utils] 该轮尚无评分，请先 round-score")
    profile = state["termination"][PROFILE_OF[node]]
    total = target_round["score"]["total"]
    scored = [r for r in state["rounds"]
              if r.get("node") == node and r.get("score") and r.get("round") <= args.round
              and (r.get("scope_id") == scope_id if scope_id else not r.get("scope_id"))]
    plateau = False
    win = profile["plateau"]["window"]
    if len(scored) >= win:
        recent = sorted(scored, key=lambda r: r["round"])[-win:]
        if max(r["score"]["total"] for r in recent) - min(r["score"]["total"] for r in recent) < profile["plateau"]["epsilon"]:
            plateau = True
    deadline = (profile.get("budget") or {}).get("deadline")
    deadline_passed, deadline_note = _deadline_passed(deadline)
    if deadline_note:
        # deadline 写了但解析不了：不能静默当作"没设截止"，否则用户以为有截止却从未生效
        print(f"[state_utils] ⚠ {deadline_note}", file=sys.stderr)

    if total >= profile["target"]:
        action = "early_stop"
        reason = f"总分 {total} >= target {profile['target']}，提前终止"
    elif args.round >= profile["max_rounds"]:
        if total >= profile["pass"]:
            action, reason = "max_rounds_pass", f"达到轮数上限 {profile['max_rounds']} 且总分 {total} >= pass {profile['pass']}，按达标合并"
        else:
            action, reason = "keep_best", f"达到轮数上限 {profile['max_rounds']} 且未达标（{total} < pass {profile['pass']}），保留历史最优"
    elif deadline_passed:
        if total >= profile["pass"]:
            action, reason = "budget_pass", f"预算截止（deadline={deadline}）且总分 {total} >= pass，按达标合并"
        else:
            action, reason = "keep_best", f"预算截止（deadline={deadline}）且未达标，保留历史最优"
    elif plateau:
        if total >= profile["pass"]:
            action, reason = "plateau_pass", f"平台期（近 {win} 轮提升 < {profile['plateau']['epsilon']}）且总分 {total} >= pass，按达标合并"
        else:
            action, reason = "keep_best", f"平台期且未达标，保留历史最优"
    elif total >= profile["pass"]:
        action, reason = "pass_continue", f"总分 {total} >= pass {profile['pass']} 但 < target {profile['target']}，保留当前最佳结果并允许继续优化"
    else:
        action, reason = "repair_and_rerun", f"总分 {total} < pass {profile['pass']}，必须依据独立评审反馈修复并重新运行"

    # DECIDE 不达标（repair_and_rerun / keep_best）→ 强制失败原因分析（根因/差距/下轮方案），缺失拒绝。
    # 该 reason 写入 decision.failure_analysis，作为下一轮 SEARCH 的根因分析输入（Deep Research 融合）。
    if action in ("repair_and_rerun", "keep_best") and not (args.reason or "").strip():
        sys.exit(
            f"[state_utils] DECIDE 未达标分支（{action}）必须提供 --reason 失败原因分析"
            "（根因/差距/下轮方案；将写入 decision.failure_analysis 供下一轮 SEARCH 根因分析输入）"
        )

    feedback = args.feedback or ""
    decision = {"action": action, "reason": reason, "feedback": feedback,
                "decided_by": "orchestrator", "timestamp": now_iso()}
    if args.reason:
        decision["failure_analysis"] = args.reason
    best = max(scored, key=lambda r: r["score"]["total"])
    if action == "keep_best":
        decision["best_round"] = best["round"]
        decision["best_total"] = best["score"]["total"]
        decision["best_branch"] = best.get("branch")
    decision["scope_id"] = scope_id
    decision["scope_key"] = target_round.get("scope_key")
    target_round["decision"] = decision
    target_round["status"] = "repair_pending" if action == "repair_and_rerun" else "completed"

    merge_actions = {"early_stop", "pass_continue", "max_rounds_pass", "budget_pass", "plateau_pass"}
    if scope_id:
        # A scoped round may finish its own DECIDE phase, but only
        # scope-promote can complete the parent node after every scope passes.
        _scope_round_phase(root, node, args.round, scope_id, "DECIDE", "completed")
        state["nodes"][node]["status"] = "in_progress"
        if action == "pass_continue":
            state["nodes"][node]["optimization_available"] = True
    else:
        if action == "pass_continue":
            state["nodes"][node]["status"] = "in_progress"
            state["nodes"][node]["optimization_available"] = True
        if action in merge_actions and action != "pass_continue":
            # 2.0.0（P0-2）：迭代节点的 completed 由本命令写入，必须走统一完成守卫。
            #
            # 🔴 但**不能查本节点门禁**——这里有真实的顺序依赖，查了就是死锁：
            #   P2/T1 由 node-review 落盘，而标准顺序是
            #   round-start → round-score → round-decide → node-review
            #   若 round-decide 要求 P2/T1 已 PASS，这两个门禁永远等不到，N4/N5 无法完成。
            # 本命令的职责是"迭代收敛判定 + 产物/上游校验"；节点级门禁验收交给随后的 node-review。
            if getattr(args, "skip_prereq", False):
                state.setdefault("meta", {}).setdefault("prereq_skips", []).append(
                    {"at": now_iso(), "node": node, "reason": "round-decide --skip-prereq（测试/迁移）"})
            else:
                from state_guard import require_completion_allowed
                require_completion_allowed(
                    root, node,
                    skills=getattr(args, "skills_read", None),
                    allow_empty=getattr(args, "allow_empty_artifacts", False),
                    allow_no_checkpoint=getattr(args, "allow_no_checkpoint", False),
                    check_own_gates=False,
                )
            state["nodes"][node]["status"] = "completed"
            state["stages"][NODES[node]["stage"]]["status"] = "completed"
            state["stages"][NODES[node]["stage"]]["completed_at"] = now_iso()

    state["decisions"].append({
        "id": f"d-{state['meta']['seq'] + 1}", "stage": NODES[node]["stage"], "round": args.round,
        "decision": action, "reason": reason, "timestamp": now_iso(),
        **({"scope_id": scope_id, "scope_key": target_round.get("scope_key")} if scope_id else {}),
    })

    upsert_row_by_first_cell(node_homepage(root, node), "迭代记录", args.round,
                             f"| {args.round} | {target_round.get('branch', '-')} | {total} | {action} | {feedback or '-'} |")
    version_path = os.path.join(root, "LogRecord", "version-update.md")
    if os.path.exists(version_path):
        append_version_update(root, f"| {now_iso()} | {node} | {args.round} | {target_round.get('branch', '-')} | {total} | {action} | {feedback or '-'} |")
    save_round_report(root, node, args.round, "decision", {
        "node": node, "round": args.round, "timestamp": now_iso(), "decided_by": "orchestrator",
        "action": action, "reason": reason, "feedback": feedback,
        "best_round": decision.get("best_round"), "best_total": decision.get("best_total"),
        "best_branch": decision.get("best_branch"),
    })
    save_state(root, state)
    refresh_dashboard(root)

    if args.git:
        require_git(root)
        r = git_commit_state(root, f"state: {node} round{args.round} 决策 {action}",
                             round_no=args.round, node=node)
        if r.returncode != 0:
            print(f"[state_utils] ⚠ git 提交失败: {r.stderr.strip()}")
        if action in merge_actions and target_round.get("branch"):
            if not do_merge(root, target_round["branch"], total):
                sys.exit("[state_utils] merge 失败，请人工处理后再继续")
    print(f"[state_utils] round-decide: node={node} round={args.round} action={action}")
    print(f"[state_utils] reason: {reason}")
    if action == "keep_best":
        print(f"[state_utils] [ESCALATE] 严重度=P1, 原因=迭代未达标且已终止（{reason}）, "
              f"反馈=保留历史最优 round{decision['best_round']}（{decision['best_total']}，分支 {decision['best_branch']}）, 建议=人工决策：换方法/降级接受/延长时间")
    elif action == "repair_and_rerun":
        print(f"[state_utils] 提示: 未达标，按独立审阅 feedback 修复后进入下一轮: {feedback or '-'}")


def do_merge(root, branch, total):
    current = git(["branch", "--show-current"], cwd=root)
    original = current.stdout.strip() if current.returncode == 0 else ""
    refs = git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=root)
    candidates = []
    if refs.returncode == 0 and refs.stdout.strip().startswith("refs/remotes/origin/"):
        candidates.append(refs.stdout.strip().rsplit("/", 1)[-1])
    candidates.extend(["main", "master", "develop"])
    target = next((name for name in dict.fromkeys(candidates)
                   if git(["show-ref", "--verify", f"refs/heads/{name}"], cwd=root).returncode == 0), None)
    if not target:
        print("[state_utils] 未找到可合并的主分支（尝试了 origin/HEAD、main、master、develop）")
        return False
    checkout = git(["checkout", target], cwd=root)
    if checkout.returncode != 0:
        print(f"[state_utils] 切回主分支失败: {checkout.stderr.strip()}")
        return False
    merged = git(["merge", "--no-ff", branch, "-m", f"merge: {branch}（评分 {total} 达标）"], cwd=root)
    if merged.returncode == 0:
        print(f"[state_utils] 已 merge {branch} 回 {target}")
        return True
    print(f"[state_utils] merge 失败: {merged.stderr.strip()}")
    if original and original != target:
        restored = git(["checkout", original], cwd=root)
        if restored.returncode != 0:
            print(f"[state_utils] ⚠ 无法恢复原分支 {original}: {restored.stderr.strip()}")
    return False


