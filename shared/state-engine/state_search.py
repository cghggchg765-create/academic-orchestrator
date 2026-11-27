"""MM state_utils —— 检索与案例命令（case-add/case-search/search-source/claim）（由 state_utils.py 拆分而来，勿手改结构；逻辑见各模块）。"""
from state_defs import *  # noqa: F401,F403
from case_search_lib import filter_cases, load_cases, locate_skill_root, score_cases

def _safe_case_id(case_id):
    """案例 ID 会拼进 state/cases/<id>.json 路径——必须防穿越。

    案例库 index.json 是外部数据（可手工编辑、可来自第三方技能包），
    原实现直接 f"{case_id}.json": `../../../ESCAPED` 能把文件写到项目外，
    绝对路径更会把 os.path.join 的 root 前缀整个吃掉。
    这里只允许字母数字开头、含 . _ - 的安全单段标识符。
    """
    from state_guard import safe_component
    value = str(case_id or "").strip()
    if not value:
        raise ValueError("案例 ID 为空")
    return safe_component(value, "case_id")


def _load_case_index(root):
    """读取 state/cases/index.json（结构不合法时报错，不静默当空索引）。"""
    index = load_json(os.path.join(root, CASES_INDEX), {"version": "1.0", "cases": []})
    if not isinstance(index, dict) or not isinstance(index.get("cases", []), list):
        sys.exit(f"[state_utils] 案例索引结构非法: {CASES_INDEX}（期望 "
                 f'{{"version": ..., "cases": [...]}}）；请修复该文件后重试')
    index.setdefault("cases", [])
    return index


def cmd_case_add(args):
    root = os.path.abspath(args.dir)
    index = _load_case_index(root)
    case_id = "case_" + uuid.uuid4().hex[:8]
    case = {"id": case_id, "title": args.title, "source": args.source, "url": args.url or "",
            "source_type": args.source_type or "", "search_query": args.query or "",
            "summary": args.summary or "", "score": args.score, "added_at": now_iso(),
            "used_in_rounds": []}
    index["cases"].append(case)
    save_json_atomic(os.path.join(root, CASES_INDEX), index)
    save_json_atomic(os.path.join(root, STATE_DIR, "cases", f"{case_id}.json"), case)
    print(f"[state_utils] case-add: {case_id} {args.title}（来源渠道: {args.source_type or '-'}，检索词: {args.query or '-'}）")


def cmd_case_search(args):
    """优秀论文案例库结构化检索（Pro 知识库 case-search）。

    检索 skills/mathematical-modeling/assets/case-library/ 的 139 张案例卡索引
    （2012—2025 CUMCM 优秀论文决策记忆）：中文二字片段 + 别名扩展 + TF-IDF 风格加权
    （问题类型/模型标签加权），支持 --top/--year/--type/--model/--json/--skill-root/--save。
    案例库定位：--skill-root（推荐）→ 环境变量 MM_SKILL_ROOT → 向上探测；均未找到时
    fail-closed 报错并提示传 --skill-root，不静默降级。命中案例可 --save 沉淀进项目
    state/cases/（证据链），供 N1 选题拆解与节点派发携带（禁止纯内生）。"""
    try:
        skill_root = locate_skill_root(args.skill_root)
    except FileNotFoundError as exc:
        sys.exit(f"[state_utils] case-search: {exc}")
    from case_search_lib import CASE_LIB_REL
    index_path = os.path.join(str(skill_root), CASE_LIB_REL)
    cases = filter_cases(load_cases(index_path), year=args.year,
                         problem_type=args.problem_type, model=args.model)
    ranked = score_cases(args.query, cases)[:max(1, args.top)]
    if args.json:
        print(json.dumps([
            {"score": round(score, 3), "matched": matched, **case}
            for score, case, matched in ranked
        ], ensure_ascii=False, indent=2))
    else:
        if not ranked:
            print("[state_utils] case-search: 未命中与查询结构相似的案例（可放宽 --type/--model 过滤后重试）。")
        for index, (score, case, matched) in enumerate(ranked, start=1):
            print(f"{index}. [{case.get('case_id', '-')}] {case.get('year', '-')} "
                  f"{case.get('paper_code') or '-'} {case.get('title', '-')}")
            print(f"   score={score:.2f}; types={', '.join(case.get('problem_types') or [])}; "
                  f"models={', '.join((case.get('models') or [])[:8])}")
            print(f"   matched={', '.join(matched[:12])}; card={case.get('card_path') or '-'}")
    # --save：把 top-N 命中沉淀进项目 state/cases/（供派发携带，禁止替换案例检索过程本身）
    if args.save:
        root = os.path.abspath(args.dir)
        index = _load_case_index(root)
        saved, rejected = 0, []
        for score, case, matched in ranked:
            # 案例库 index.json 是外部数据：ID 必须先校验，否则 `../../x` / 绝对路径
            # 会让 os.path.join(root, ...) 写到项目外（Windows 上还会吃掉 root 前缀）。
            try:
                case_id = "pro_" + _safe_case_id(case["case_id"].replace("-", ""))
            except (KeyError, SystemExit, ValueError) as exc:
                rejected.append(f"{case.get('case_id')!r}: {exc}")
                continue
            if any(existing.get("id") == case_id for existing in index["cases"]):
                continue
            record = {"id": case_id, "title": case["title"], "source": case.get("card_path") or "",
                      "url": case.get("source_page") or "", "source_type": "pro-case-library",
                      "search_query": args.query, "summary": (case.get("core_problem") or "")[:300],
                      "score": round(score, 3), "added_at": now_iso(), "used_in_rounds": [],
                      "problem_types": case.get("problem_types") or [],
                      "models": case.get("models") or []}
            index["cases"].append(record)
            save_json_atomic(os.path.join(root, STATE_DIR, "cases", f"{case_id}.json"), record)
            saved += 1
        save_json_atomic(os.path.join(root, CASES_INDEX), index)
        print(f"[state_utils] case-search --save: 沉淀 {saved} 张命中案例到 state/cases/（证据链，共 {len(index['cases'])} 条）")
        if rejected:
            print("[state_utils] ⚠ 以下案例 ID 非法（含路径分隔/穿越或保留字符），已跳过未落盘："
                  + "；".join(rejected[:5]), file=sys.stderr)


def cmd_search_source_add(args):
    root = os.path.abspath(args.dir)
    doc = load_json(os.path.join(root, SEARCH_SOURCES_FILE), {"version": "1.0", "sources": []})
    entry = {"id": args.id, "type": args.type, "name": args.name, "address": args.address,
             "tool": args.tool or "-", "query_template": args.query_template or "",
             "apply_when": [x.strip() for x in (args.apply_when or "").split(",") if x.strip()],
             "priority": args.priority or 9}
    for i, s in enumerate(doc["sources"]):
        if s.get("id") == args.id:
            doc["sources"][i] = entry
            save_json_atomic(os.path.join(root, SEARCH_SOURCES_FILE), doc)
            print(f"[state_utils] search-source: 已更新渠道 {args.id}")
            return
    doc["sources"].append(entry)
    save_json_atomic(os.path.join(root, SEARCH_SOURCES_FILE), doc)
    print(f"[state_utils] search-source: 已新增渠道 {args.id}")


def cmd_search_evidence(args):
    """检索证据派发清单：汇总该节点知识卡片 + 案例 + GB/T 7714 台账 + MCP 调用留痕。

    派发对应 Agent 时携带：执行 Agent 以知识卡片/案例为外部依据，禁止纯内生输出。"""
    root = os.path.abspath(args.dir)
    require_node(args.node)
    node = args.node
    evidence = mcp_search_evidence(root, node)
    cards = []
    cards_dir = os.path.join(root, STATE_DIR, "reports", "mcp-cards")
    if os.path.isdir(cards_dir):
        cards = sorted(n for n in os.listdir(cards_dir)
                       if n.lower().endswith((".md", ".json")))
    ledger = os.path.join(root, STATE_DIR, "reports", "references-ledger.md")
    print(f"# {node} 检索证据派发清单（{NODES[node]['name']}）")
    print(f"- MCP 必调: {MCP_MANDATORY_NODES.get(node, '(非核心节点，按需调用)')}")
    print(f"- 检索留痕: {'；'.join(evidence) if evidence else '(无 —— 核心节点必须先补 SEARCH 再评分/审阅 PASS)'}")
    print(f"- 知识卡片（{len(cards)}）: {'、'.join(cards) if cards else '(无)'}")
    print(f"- GB/T 7714 台账: {'存在 ' + os.path.abspath(ledger) if os.path.exists(ledger) else '（缺失）'}")
    print(f"- 派发建议：委派 {node} 时，将上述知识卡片/案例路径随派发 prompt 分发给"
          f" 执行 {NODES[node]['executor']} / 审阅 {NODES[node]['reviewer'] or '-'}（禁止纯内生）")


def _claim_ttl_seconds(raw, default=3600):
    """claim.json 的 ttl_s 可能是字符串/负数/None（手工编辑、旧版本残留）。

    原实现直接拿原始值参与 `< ttl` 比较，ttl_s 为字符串时抛
    TypeError: '<' not supported between 'float' and 'str'，整个跨 agent 互斥
    扫描直接崩掉 → 认领互斥失效（或命令异常退出）。这里统一转成合法数值。
    """
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _active_claims_for_node(root, node, exclude_agent=None):
    """扫描 state/agents/*/claim.json，返回该节点上未过期且属于其他 agent 的租约。

    2.0.0 修复：原实现只读自己 agent 的 claim.json，导致两个不同 agent 可同时
    认领同一节点（"防重复派发"实际失效）。改为跨 agent 扫描。
    """
    agents_dir = os.path.join(root, STATE_DIR, "agents")
    active = []
    if not os.path.isdir(agents_dir):
        return active
    for name in os.listdir(agents_dir):
        if exclude_agent and name == exclude_agent:
            continue
        path = os.path.join(agents_dir, name, "claim.json")
        if not os.path.isfile(path):
            continue
        try:
            c = json.loads(open(path, encoding="utf-8").read())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(c, dict) or c.get("node") != node:
            continue
        try:
            claimed = datetime.fromisoformat(str(c["claimed_at"]).replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        if claimed.tzinfo is None:
            claimed = claimed.replace(tzinfo=timezone.utc)
        ttl = _claim_ttl_seconds(c.get("ttl_s", 3600))
        if (datetime.now(timezone.utc) - claimed).total_seconds() < ttl:
            active.append({"agent": c.get("agent_id", name), "claimed_at": c.get("claimed_at"),
                           "ttl_s": ttl, "round": c.get("round")})
    return active


def _reject_windows_name_collision(value, label):
    """拒绝 Windows 上会折叠到同一个路径的标识符（委托 state_events 的同一实现）。

    `abc` 与 `abc.` / `abc ` 在 Windows 上落到同一个目录（尾点尾空格被静默剥离），
    实测两个不同 agent_id 会共用同一份 claim.json，互相顶替租约；
    CON/PRN/NUL/AUX/COM1… 这类设备名会让后续 open 出现怪异行为。
    safe_component 的正则允许尾点和这些名字，因此在这层补上。
    """
    from state_events import _require_agent_id
    return _require_agent_id(value, label)


def cmd_claim(args):
    root = os.path.abspath(args.dir)
    require_node(args.node)
    state = load_state(root)
    node = args.node
    try:
        ttl = int(getattr(args, "ttl", 3600) or 3600)
    except (TypeError, ValueError):
        sys.exit(f"[state_utils] 非法 --ttl: {getattr(args, 'ttl', None)!r}（须为正整数秒）")
    if ttl <= 0:
        sys.exit(f"[state_utils] 非法 --ttl: {ttl}（须为正整数秒）")
    # P0-8：agent_id 会拼进目录路径，必须校验，否则 `claim "../../../EVIL"` 可写出项目外
    from state_guard import safe_component, assert_within
    safe_component(args.agent_id, "agent_id")
    _reject_windows_name_collision(args.agent_id, "agent_id")
    claim_dir = os.path.join(root, STATE_DIR, "agents", args.agent_id)
    assert_within(root, claim_dir, "claim 目录")
    claim_path = os.path.join(claim_dir, "claim.json")

    # ① 同一 agent 重复认领同一节点：未过期则拒绝
    old = load_json(claim_path)
    if isinstance(old, dict) and old.get("node") == node:
        try:
            claimed = datetime.fromisoformat(str(old["claimed_at"]).replace("Z", "+00:00"))
            if claimed.tzinfo is None:
                claimed = claimed.replace(tzinfo=timezone.utc)
            old_ttl = _claim_ttl_seconds(old.get("ttl_s", 3600))
            if (datetime.now(timezone.utc) - claimed).total_seconds() < old_ttl:
                sys.exit(f"[state_utils] 节点 {node} 你已有有效租约（{old.get('claimed_at')} 认领，"
                         f"ttl={old_ttl}s），拒绝重复认领。如需续期请先等过期或换节点。")
        except (ValueError, KeyError):
            pass

    # ② 跨 agent 互斥：该节点已被其他 agent 占用（未过期）→ 拒绝
    others = _active_claims_for_node(root, node, exclude_agent=args.agent_id)
    if others and not getattr(args, "force", False):
        detail = "; ".join(f"{c['agent']}@{c['claimed_at']}(ttl={c['ttl_s']}s)" for c in others)
        sys.exit(f"[state_utils] 节点 {node} 已被其他 Agent 认领，拒绝重复派发：{detail}\n"
                 f"  如确认对方已失联，可加 --force 抢占（会在 rounds 留痕）。")

    rounds = [r for r in state["rounds"] if r.get("node") == node and r.get("status") == "in_progress"]
    round_no = rounds[-1]["round"] if rounds else None
    claim = {"agent_id": args.agent_id, "node": node, "round": round_no,
             "claimed_at": now_iso(), "ttl_s": ttl}
    if others:
        claim["preempted"] = [c["agent"] for c in others]
    save_json_atomic(claim_path, claim)
    if rounds:
        rounds[-1].setdefault("agent_claims", []).append(
            {"agent": args.agent_id, "claimed_at": now_iso(),
             **({"preempted": claim["preempted"]} if others else {})})
        save_state(root, state)
    print(f"[state_utils] claim: {args.agent_id} @ {node} round={round_no} ttl={ttl}s"
          + (f"（抢占 {claim['preempted']}）" if others else ""))

def cmd_dr_note(args):
    """登记一次 Deep Research 介入（Deep Research 链嵌入迭代环的可审计留痕）。

    记录节点/轮次/阶段（SEARCH/SCORE/DECIDE/NODE）与链角色
    （research_architect / literature / researcher / synthesis / report_compiler）、
    待解决问题、输入与产出，追加到 state/reports/dr-interventions.jsonl；
    若为迭代轮次则同步进 rounds[n].deep_research。N8 终检可 dr-list 核对"每轮有据介入"。"""
    root = os.path.abspath(args.dir)
    require_node(args.node)
    state = load_state(root)
    node = args.node
    dr = {
        "ts": now_iso(),
        "node": node,
        "round": args.round,
        "phase": (args.phase or "NODE").upper(),
        "role": args.role,
        "topic": args.topic,
        "input": args.input or "",
        "output": args.output or "",
        "ref": args.ref or "",
    }
    path = os.path.join(root, DR_INTERVENTIONS_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(dr, ensure_ascii=False) + "\n")
    if args.round is not None:
        for r in state["rounds"]:
            if r.get("node") == node and r.get("round") == args.round:
                r.setdefault("deep_research", []).append(dr)
                break
        save_state(root, state)
    print(f"[state_utils] dr-note: {node}"
          + (f" round{args.round}" if args.round is not None else "")
          + f" phase={dr['phase']} role={dr['role']} topic={args.topic}")


def cmd_dr_list(args):
    """列出节点（+可选轮次）的 Deep Research 介入留痕（dr-interventions.jsonl + rounds[n].deep_research 汇总）。"""
    root = os.path.abspath(args.dir)
    require_node(args.node)
    node = args.node
    entries = []
    path = os.path.join(root, DR_INTERVENTIONS_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("node") == node and (args.round is None or rec.get("round") == args.round):
                    entries.append(rec)
    # 汇总轮次内嵌介入（dr-note 已同步 rounds[n].deep_research，这里并集去重展示）
    state = load_state(root)
    for r in state["rounds"]:
        if r.get("node") == node and (args.round is None or r.get("round") == args.round):
            for rec in (r.get("deep_research") or []):
                if rec not in entries:
                    entries.append(rec)
    entries.sort(key=lambda e: e.get("ts", ""))
    print(f"# {node}" + (f" round{args.round}" if args.round is not None else "") + f" Deep Research 介入留痕（{len(entries)} 条）")
    for e in entries:
        print(f"- [{e.get('ts')}] round={e.get('round') or '-'} phase={e.get('phase')} role={e.get('role')} "
              f"topic={e.get('topic')} ref={e.get('ref') or '-'} output={e.get('output') or '-'}")


# ---------------------------------------------------------------- main


