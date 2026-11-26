"""MM state_utils —— 节点生命周期命令（node-start/finish/log/todo）（由 state_utils.py 拆分而来，勿手改结构；逻辑见各模块）。"""
from state_defs import *  # noqa: F401,F403
from state_scaffold import *  # noqa: F401,F403

def cmd_node_start(args):
    root = os.path.abspath(args.dir)
    require_node(args.node)
    state = load_state(root)
    node = args.node

    # ---- 注册表一致性校验 ----
    registry = load_registry(root)
    registry_ids = set(registry.keys())
    nodedef_ids = set(k for k in NODES if k != "N0")
    missing_in_registry = nodedef_ids - registry_ids
    extra_in_registry = registry_ids - nodedef_ids
    inconsistencies = []
    if missing_in_registry:
        inconsistencies.append(f"registry 缺少节点: {', '.join(sorted(missing_in_registry))}")
    if extra_in_registry:
        inconsistencies.append(f"registry 多余节点: {', '.join(sorted(extra_in_registry))}")
    common = nodedef_ids & registry_ids
    for nid in common:
        r_entry = registry[nid]
        d_entry = NODES[nid]
        if r_entry.get("executor") != d_entry.get("executor"):
            inconsistencies.append(f"节点 {nid} executor 不匹配: registry={r_entry.get('executor')}, NODES={d_entry.get('executor')}")
        if r_entry.get("reviewer") != d_entry.get("reviewer"):
            inconsistencies.append(f"节点 {nid} reviewer 不匹配: registry={r_entry.get('reviewer')}, NODES={d_entry.get('reviewer')}")
        if normalized_skill_set(r_entry.get("required_skills", [])) != normalized_skill_set(d_entry.get("skills", [])):
            inconsistencies.append(f"节点 {nid} skills 不匹配")
        if sorted(r_entry.get("gates", [])) != sorted(d_entry.get("gates", [])):
            inconsistencies.append(f"节点 {nid} gates 不匹配")
        if r_entry.get("artifact_dir") != d_entry.get("artifact"):
            inconsistencies.append(f"节点 {nid} artifact 不匹配: registry={r_entry.get('artifact_dir')}, NODES={d_entry.get('artifact')}")
    if inconsistencies:
        msg = "; ".join(inconsistencies)
        sys.exit(f"[state_utils] 注册表与 NODES 定义不一致: {msg}")

    # ---- 上游前置校验（N0 例外） ----
    if node != "N0":
        verify_problem_lock(root)
        missing = []
        for up_node, up_name in UPSTREAM.get(node, []):
            up_status = state["nodes"].get(up_node, {}).get("status", "pending")
            if up_status != "completed":
                missing.append(f"上游节点 {up_node}({up_name}) 状态为 {up_status}，需要 completed")
            # 上游审阅门禁校验（防"阶段不完全/修改不完善就进下一步"）：上游必须已通过独立审阅循环
            up_gate = REVIEW_GATE.get(up_node)
            if up_gate:
                up_gate_status = (state["gates"].get(up_gate) or {}).get("status", "pending")
                if up_gate_status not in {"PASS", "auto_passed", "confirmed"}:
                    missing.append(f"上游节点 {up_node} 审阅门禁 {up_gate}={up_gate_status}"
                                   f"（未通过/未审阅）——必须先完成'审阅→修改→再审阅'循环（PASS）再开工 {node}")
            # 检查静态 artifact 是否存在
            up_artifact = NODES.get(up_node, {}).get("artifact", "")
            for art_path in up_artifact.split(","):
                art_path = art_path.strip()
                if not art_path:
                    continue
                full = os.path.join(root, art_path)
                if not os.path.exists(full):
                    missing.append(f"上游节点 {up_node} 的产物 {art_path} 不存在")
        if missing:
            info = "; ".join(missing)
            sys.exit(f"[state_utils] 前置条件未满足: {info}")

    state["nodes"][node]["status"] = "in_progress"
    if args.goal:
        state["nodes"][node]["goal"] = args.goal
    state["meta"]["current_stage"] = NODES[node]["stage"]
    # 技能派发清单门禁（协调层 → 专业 skill）：非 N0 节点开工前必须有本轮派发清单。
    # 清单由 skill-plan 生成；缺失时此处自动按当前机器已装 skill 生成一份（等价于
    # "任务开始前的 skill 分析"），并把结果写进节点记录，事后可核对是否真的调用。
    # 显式豁免：--no-skill-routing（离线/试验环境），豁免会写入节点记录留痕。
    if node != "N0":
        manifest_path = os.path.join(root, STATE_DIR, "skill-routing", f"{node}.json")
        state["nodes"][node].pop("skill_routing_waived", None)
        if getattr(args, "no_skill_routing", False):
            state["nodes"][node]["skill_routing_waived"] = {
                "at": now_iso(), "reason": "node-start --no-skill-routing",
            }
        else:
            if getattr(args, "replan", False) or not os.path.isfile(manifest_path):
                try:
                    from state_skills import build_manifest
                    manifest = build_manifest(root, node)
                    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
                    save_json_atomic(manifest_path, manifest)
                    print(f"[state_utils] 已生成本节点专业 skill 派发清单: "
                          f"{os.path.relpath(manifest_path, root)}")
                    if manifest.get("must_load"):
                        print("[state_utils] 本节点应加载: " + ", ".join(manifest["must_load"]))
                    if manifest.get("unresolved"):
                        print("[state_utils] ⚠ 本机无匹配 skill 的能力: "
                              + "；".join(manifest["unresolved"]))
                except Exception as exc:  # 路由层缺失不应阻断建模主流程
                    print(f"[state_utils] ⚠ 技能路由不可用（{exc}）；本节点按 required_skills 执行")
            with open(manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
            state["nodes"][node]["skill_manifest"] = {
                "generated_at": manifest.get("generated_at"),
                "must_load": manifest.get("must_load", []),
                "unresolved": manifest.get("unresolved", []),
            }
    # W1 落盘（消除断链）：N7 写作开工时若上游图表审阅 V1 已通过 → "每个主张有图表/输出支撑"前置就绪
    if node == "N7":
        v1 = (state["gates"].get("V1") or {}).get("status")
        if v1 in {"PASS", "auto_passed", "confirmed"}:
            w1 = state["gates"].setdefault("W1", {"status": "pending"})
            w1.update({"status": "PASS", "agent": "orchestrator", "timestamp": now_iso(),
                       "result": f"N7 开工时上游 V1={v1}，写作前置支撑（主张↔图表/输出）判定就绪"})
    save_state(root, state)
    update_homepage_meta(node_homepage(root, node), "in_progress")
    # 交接文件自动刷新（独立拉出/断点恢复时先读 handoff.md 自检）
    try:
        handoff = write_handoff(root, node)
        print(f"[state_utils] handoff 已刷新: {os.path.relpath(handoff, root)}")
    except Exception:
        pass
    refresh_dashboard(root)
    print(f"[state_utils] node {node} -> in_progress")


def cmd_node_finish(args):
    root = os.path.abspath(args.dir)
    require_node(args.node)
    state = load_state(root)
    node = args.node
    stage = NODES[node]["stage"]
    # 执行 Agent 校验（防主 agent 内联代做）：非 N0 必须声明执行者且与 registry executor 匹配
    executor = args.agent or ("orchestrator" if node == "N0" else "")
    if not executor:
        sys.exit(f"[state_utils] node-finish 必须指定 --agent（执行该节点的 Agent；N0 可省）")
    if executor != NODES[node]["executor"]:
        sys.exit(f"[state_utils] 节点 {node} 由 {NODES[node]['executor']} 执行，实际声明 {executor}（禁止错 Agent 代做）")
    # 技能声明校验（强制子 Agent 先加载本节点 required_skills；前缀/裸名两种写法等价）
    if node != "N0":
        declared = normalized_skill_set((args.skills or "").split(","))
        required_list = NODES[node].get("skills", [])
        missing_keys = normalized_skill_set(required_list) - declared
        if missing_keys:
            missing = [s for s in required_list if skill_basename(s) in missing_keys]
            sys.exit(f"[state_utils] 执行 Agent 必须声明已加载技能（--skills），缺失: {', '.join(missing)}")
        # 派发清单门禁：动态选出的专业 skill 也必须实际加载（协调层选择 → 执行层落实）
        if not state["nodes"][node].get("skill_routing_waived"):
            manifest_path = os.path.join(root, STATE_DIR, "skill-routing", f"{node}.json")
            if os.path.isfile(manifest_path):
                with open(manifest_path, encoding="utf-8") as fh:
                    manifest = json.load(fh)
                must = normalized_skill_set(manifest.get("must_load", []))
                not_loaded = must - declared
                if not_loaded:
                    sys.exit(
                        f"[state_utils] 节点 {node} 未加载派发清单要求的专业 skill: "
                        f"{', '.join(sorted(not_loaded))}"
                        f"（清单见 state/skill-routing/{node}.json；"
                        f"若清单已过期请重跑 skill-plan {node} --apply）"
                    )
    # 迭代节点强制走迭代环：无进行中 round 时禁止直接标 completed
    if node in PROFILE_OF:
        has_round = any(r.get("node") == node and r.get("status") == "in_progress" for r in state["rounds"])
        if not has_round:
            sys.exit(f"[state_utils] 迭代节点 {node} 必须通过 round-start 开启迭代环（SEARCH→DECIDE），"
                     f"禁止直接 node-finish 标完成")
    in_iter = node in PROFILE_OF and any(
        r.get("node") == node and r.get("status") == "in_progress" for r in state["rounds"])
    if in_iter:
        print(f"[state_utils] 节点 {node} 处于迭代轮次中：仅登记产物并刷新首页，completed 状态由 round-decide（early_stop/达标终止）决定")
    else:
        state["nodes"][node]["status"] = "completed"
        state["stages"][stage]["status"] = "completed"
        state["stages"][stage]["completed_at"] = now_iso()
    state["nodes"][node]["goal"] = ""
    state["nodes"][node]["executed_by"] = executor
    if node != "N0":
        state["nodes"][node]["skills_used"] = [s.strip() for s in (args.skills or "").split(",") if s.strip()]
    # 产物快照登记：级联失效（cascade-invalidate）据此检测上游变更 → 下游联动重置
    state["nodes"][node]["artifact_hash"] = artifact_snapshot(root, node)
    for art in args.artifact or []:
        if art not in state["stages"][stage].setdefault("artifacts", []):
            state["stages"][stage]["artifacts"].append(art)
    save_state(root, state)
    for art in args.artifact or []:
        full = os.path.join(root, art)
        if os.path.isfile(full):
            upsert_row_by_first_cell(node_homepage(root, node), "产物清单", art,
                                     f"| {art} | {sha256_of(full)[:12]} | - |")
    update_homepage_meta(node_homepage(root, node), state["nodes"][node]["status"])
    refresh_dashboard(root)
    print(f"[state_utils] node {node} -> {state['nodes'][node]['status']}（执行 Agent: {executor}）")


def cmd_node_log(args):
    """记录节点执行小步骤（追加到 state/nodes/<name>/steps.md，时间线留痕；配合 todo 动态更新进度）。"""
    root = os.path.abspath(args.dir)
    require_node(args.node)
    step = (args.step or "").strip()
    if not step:
        sys.exit("[state_utils] node-log 必须提供 --step <小步骤描述>")
    node = args.node
    by = (args.by or NODES[node]["executor"]).strip()
    steps_file = os.path.join(root, STATE_DIR, "nodes", NODES[node]["dir"], "steps.md")
    os.makedirs(os.path.dirname(steps_file), exist_ok=True)
    line = f"- [{now_iso()}] ({by}) {step}"
    if not os.path.exists(steps_file):
        save_text_atomic(steps_file, f"# {node}-{NODES[node]['name']} 执行小步骤记录\n\n{line}\n")
    else:
        with open(steps_file, "r", encoding="utf-8") as f:
            text = f.read()
        save_text_atomic(steps_file, text.rstrip("\n") + f"\n{line}\n")
    print(f"[state_utils] node-log: {node} 已记录小步骤 -> {os.path.relpath(steps_file, root)}")


def _todo_lines(root):
    path = os.path.join(root, TODO_FILE)
    lines = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    return path, lines


def cmd_todo(args):
    """项目任务清单动态更新：add 新增 / done 标记完成 / list 列出 / plan 按状态自动规划。"""
    root = os.path.abspath(args.dir)
    action = args.action
    path, lines = _todo_lines(root)
    if action == "add":
        item = (args.item or "").strip()
        if not item:
            sys.exit("[state_utils] todo add 必须提供 <待办描述>")
        tag = f"[{args.node}] " if getattr(args, "node", "") else ""
        line = f"- [ ] {tag}{item}"
        if any(l.strip() == line for l in lines):
            print(f"[state_utils] todo: 已存在相同条目，跳过: {line}")
            return
        text = ("# 任务清单（To-Do）\n\n" if not lines else "\n".join(lines).rstrip("\n") + "\n") + line + "\n"
        save_text_atomic(path, text)
        print(f"[state_utils] todo add: {line}")
    elif action == "done":
        pat = (args.item or "").strip()
        if not pat:
            sys.exit("[state_utils] todo done 必须提供匹配文本")
        hit, out = False, []
        for ln in lines:
            if not hit and ln.strip().startswith("- [ ]") and pat in ln:
                out.append(ln.replace("- [ ]", "- [x]", 1) + f" ({now_iso()})")
                hit = True
            else:
                out.append(ln)
        if not hit:
            sys.exit(f"[state_utils] todo done: 未找到含 '{pat}' 的未完成条目（todo list 查看）")
        save_text_atomic(path, "\n".join(out).rstrip("\n") + "\n")
        print(f"[state_utils] todo done: {pat}")
    elif action == "plan":
        if not os.path.exists(os.path.join(root, STATE_FILE)):
            sys.exit(f"[state_utils] 项目未初始化：{root}；请先运行 init")
        state = load_state(root)
        nodes, gates = state.get("nodes", {}), state.get("gates", {})
        added, done = 0, 0
        for nid, info in NODES.items():
            if nid == "N0":
                continue
            status = (nodes.get(nid) or {}).get("status", "pending")
            # 执行任务：completed → 标完成；否则确保待办存在
            exec_line = f"- [ ] [{nid}] {info['name']} 执行（{info['executor']}）"
            exec_done = f"- [x] [{nid}] {info['name']} 执行（{info['executor']}）"
            if status == "completed":
                if any(l.strip() == exec_line for l in lines):
                    idx = next(i for i, l in enumerate(lines) if l.strip() == exec_line)
                    lines[idx] = exec_line.replace("- [ ]", "- [x]", 1) + f" ({now_iso()})"
                    done += 1
                elif not any(l.strip().startswith(exec_done[:-1]) for l in lines):
                    lines.append(exec_done + f" ({now_iso()})")
                    done += 1
            else:
                if not any(l.strip() in (exec_line, exec_done) or l.strip().startswith(f"- [x] [{nid}] {info['name']} 执行")
                           for l in lines):
                    lines.append(exec_line)
                    added += 1
            # 审阅任务：对应门禁已通过 → 标完成；否则确保待办存在
            gate_id = REVIEW_GATE.get(nid)
            gate_ok = gate_id and (gates.get(gate_id) or {}).get("status") in {"PASS", "confirmed", "auto_passed"}
            rev = info.get("reviewer") or "-"
            rev_line = f"- [ ] [{nid}] {info['name']} 审阅（{rev}）"
            rev_done = f"- [x] [{nid}] {info['name']} 审阅（{rev}）"
            if gate_ok:
                if any(l.strip() == rev_line for l in lines):
                    idx = next(i for i, l in enumerate(lines) if l.strip() == rev_line)
                    lines[idx] = rev_line.replace("- [ ]", "- [x]", 1) + f" ({now_iso()})"
                    done += 1
                elif not any(l.strip().startswith(rev_done[:-1]) for l in lines):
                    lines.append(rev_done + f" ({now_iso()})")
                    done += 1
            else:
                if not any(l.strip() in (rev_line, rev_done) or l.strip().startswith(f"- [x] [{nid}] {info['name']} 审阅")
                           for l in lines):
                    lines.append(rev_line)
                    added += 1
        save_text_atomic(path, "\n".join(lines).rstrip("\n") + "\n")
        remaining = sum(1 for l in lines if l.strip().startswith("- [ ]"))
        print(f"[state_utils] todo plan: 新增 {added} 条 / 标记完成 {done} 条 / 剩余未完成 {remaining} 条")
        print(f"[state_utils] 提示: 完整流程含全部 8 个执行任务 + 8 个审阅任务；修改算法/模型后运行 cascade-invalidate 让下游任务回到待办。")
    else:  # list
        if not os.path.exists(path):
            print("# 任务清单（To-Do）\n\n（空）")
            return
        with open(path, "r", encoding="utf-8") as f:
            print(f.read())


