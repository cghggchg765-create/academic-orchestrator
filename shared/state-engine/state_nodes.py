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
        # 单一实现：上游 completed + 全部门禁 PASS + 产物哈希未漂移 + 产物存在
        # 由 state_guard.check_upstream 统一判定（此前本函数另写一套，漏了漂移检查，
        # 导致"审阅后偷改上游产物"在 node-start 路径上完全不被拦截）。
        from state_guard import check_upstream
        missing = check_upstream(root, node, state, require_artifact_present=True)
        if missing:
            sys.exit(
                f"[state_utils] 拒绝 node-start {node}：前置条件未满足（上游 {len(missing)} 项）：\n  - "
                + "\n  - ".join(missing)
                + f"\n  修法：先补齐上游产物/门禁，或重跑上游审阅 "
                  f"（python state/state_utils.py node-review <up_node> --agent <审阅Agent> "
                  f"--result PASS --skills \"<必读skill>\" --evidence <证据路径>）。"
            )

    state["nodes"][node]["status"] = "in_progress"
    # P1-10：记录开工时的产物快照，作为"是否真的产出"的基准。
    # 有了它，脚手架预建文件天然不算产出（快照未变 = 没做任何事），
    # 不需要再靠逐个列哨兵字符串去猜哪些文件是占位。
    if node != "N0":
        state["nodes"][node]["start_artifact_hash"] = artifact_snapshot(root, node)
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
    # 执行 Agent 校验（防内联代做）：非 N0 必须声明执行者且与 registry executor 匹配。
    # N0 为项目初始化，2.0.0 起由主 Agent 完成，executor 记为 NODES 中声明的 main-agent。
    executor = args.agent or (NODES[node]["executor"] if node == "N0" else "")
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
    state["nodes"][node]["goal"] = ""
    state["nodes"][node]["executed_by"] = executor
    if node != "N0":
        state["nodes"][node]["skills_used"] = [s.strip() for s in (args.skills or "").split(",") if s.strip()]
    # 2.0.0（P0-3）：非 N0 必须曾经 node-start。否则 start_artifact_hash 缺失、
    # skill 派发清单未生成，后续技能校验与上游校验都会被静默跳过。
    # --skip-prereq 与 round-start/round-decide/result-ingest 同一开关语义：
    # 跳过"未开工 + 上游"两段前置守卫，仅供单测/历史项目迁移，写入 meta.prereq_skips 留痕。
    # 注意：这里**不查本节点门禁**——node-finish 是"登记产物、交件待审"，
    # 门禁由随后的 node-review 落盘（执行顺序：node-finish → node-review → 门禁 PASS）。
    # 若在此要求门禁已过，正常流程永远无法推进。
    from state_guard import check_not_started, check_upstream
    if getattr(args, "skip_prereq", False):
        state.setdefault("meta", {}).setdefault("prereq_skips", []).append(
            {"at": now_iso(), "node": node, "reason": "node-finish --skip-prereq（测试/迁移）"})
    else:
        msg = check_not_started(root, node, state)
        if msg:
            sys.exit(msg)
        # 上游 completed + 门禁 PASS + 产物未漂移（防"审阅后改上游"）
        up_errs = check_upstream(root, node, state)
        if up_errs:
            sys.exit(f"[state_utils] 拒绝 node-finish {node}（上游 {len(up_errs)} 项不满足）：\n  - "
                     + "\n  - ".join(up_errs))
    # 2.0.0 分阶段归档 + 产物存在性校验：抽成共享函数，保证 round-decide /
    # scope-promote 等"另一条标 completed 的路径"也执行同一套校验（P1-8）。
    require_node_deliverables(
        root, node,
        allow_empty=getattr(args, "allow_empty_artifacts", False),
        allow_no_checkpoint=getattr(args, "allow_no_checkpoint", False),
    )
    if getattr(args, "allow_empty_artifacts", False):
        try:
            from state_events import record_exemption
            record_exemption(root, "allow-empty-artifacts", node, executor)
        except Exception:
            pass
    # 状态写入放在全部校验之后：此前 166 行就先写 completed 到内存，
    # 靠"校验失败 sys.exit 不落盘"保证安全——隐式契约，一旦有人在校验前加
    # save_state 就会静默写入未校验状态。现在改为校验通过后才置 completed。
    if not in_iter:
        state["nodes"][node]["status"] = "completed"
        state["stages"][stage]["status"] = "completed"
        state["stages"][stage]["completed_at"] = now_iso()
    # 产物快照登记：级联失效（cascade-invalidate）据此检测上游变更 → 下游联动重置
    state["nodes"][node]["artifact_hash"] = artifact_snapshot(root, node)
    for art in args.artifact or []:
        if art not in state["stages"][stage].setdefault("artifacts", []):
            state["stages"][stage]["artifacts"].append(art)
    # 2.0.0：把产物自动登记进 artifacts-registry（不再依赖子 Agent 记得手动调用）。
    # 这样 artifacts-registry 成为真实台账，orphan-scan 与后续审计才有据可查。
    _auto_register_outputs(root, node, executor)
    save_state(root, state)
    for art in args.artifact or []:
        full = os.path.join(root, art)
        if os.path.isfile(full):
            upsert_row_by_first_cell(node_homepage(root, node), "产物清单", art,
                                     f"| {art} | {sha256_of(full)[:12]} | - |")
    update_homepage_meta(node_homepage(root, node), state["nodes"][node]["status"])
    refresh_dashboard(root)
    print(f"[state_utils] node {node} -> {state['nodes'][node]['status']}（执行 Agent: {executor}）")


PLACEHOLDER_NAMES = {".gitkeep", "readme.txt", ".gitignore"}
# 脚手架预建的模板文件：存在不代表"有产出"。用哨兵字符串判定是否仍是未填写的空模板。
#
# 哨兵必须取自 state_scaffold.standard_files_content() 实际写入的正文，
# 否则模板被当成真实产出（实测：modeldocs/reference-list.md 的正文是
# "# reference-list（参考文献清单）"，不含"待填写/占位"，旧表把它判成已填写）。
# 每个条目只需命中任一哨兵即视为未填写。
SCAFFOLD_TEMPLATES = {
    "data/datalog.md": ("产物占位", "待 N2 数据处理后填写"),
    "resultfigures/figure-list.md": ("由 visualization agent 维护", "| - | - | - | - | - | - | - | - | - | - | - | - |"),
    "modeldocs/model-framework.md": ("产物占位",),
    "modeldocs/formula.md": ("产物占位",),
    "modeldocs/assumption.md": ("产物占位",),
    "modeldocs/reference-list.md": ("# reference-list（参考文献清单）",),
    "modeldocs/sensitivity-analysis.md": ("产物占位",),
    "modeldocs/error-analysis.md": ("产物占位",),
    "modeldocs/model-validation.md": ("产物占位",),
    "submissionpackage/参赛提交清单.md": ("| 待核对 |", "由 reviewer（N8 终审）核对生成"),
    "logrecord/daily-log.md": ("| 日期 | 进度 | 问题 | 解决方案 |",),
    "logrecord/bug-fix-log.md": ("| 时间 | 现象 | 根因 | 修复 | 关联分支 |",),
    "logrecord/version-update.md": ("由迭代引擎每轮自动追加",),
    # N1 产物同样是脚手架预建占位
    "probleminfo/problemnotes.md": ("待 N1 选题拆解后填写", "产物占位"),
    "probleminfo/keyrequirements.md": ("产物占位",),
    # N4 代码骨架：只把 main.py 里那句"占位模板: 请在 Code/problem_"当占位标志。
    # 这是模板独有的整句，用户实现后自然删掉；不用泛词"占位模板"（docstring 里也有）。
    # config.py 不列入：它的内容（路径常量 + 种子）用户"填完"后与模板几乎一致，
    # 任何基于文本的判据都会误报——代码是否有产出交给 code_structure_audit.py 判。
    "code/main.py": ("占位模板: 请在 Code/problem_",),
}
# 代码骨架占位：problem_N/*.py 与 visualization/*.py 里的 stub 标记
CODE_STUB_MARKERS = ("NotImplementedError", "TODO: implement")


def _is_filled(path, rel):
    """判断文件是否为真实产出（非占位文件、非未填写的空模板、非未实现的代码 stub）。"""
    base = os.path.basename(path).lower()
    if base in PLACEHOLDER_NAMES:
        return False
    # 空文件 / 只有空白：不是产出。零字节文件此前被记为"已产出"，
    # 于是 `touch Data/x.txt` 就能让节点过产物门禁。
    try:
        if os.path.getsize(path) == 0:
            return False
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            body = fh.read()
    except OSError:
        return False
    if not body.strip():
        return False
    norm = rel.replace("\\", "/").lower()
    markers = SCAFFOLD_TEMPLATES.get(norm)
    if markers and any(m in body for m in markers):
        return False
    # 代码文件：脚手架生成的骨架都带 NotImplementedError/TODO 占位
    if norm.endswith(".py") and ("/problem_" in norm or "/visualization/" in norm):
        if any(m in body for m in CODE_STUB_MARKERS):
            return False
    return True


def _count_node_outputs(root, node):
    """统计节点声明产物目录下的真实产出数。

    判定顺序（P1-10 根本方案）：
      1. 若节点记录了 start_snapshot（node-start 时的产物快照），
         则"真实产出 = 当前快照中比开工时**新增/变大**的产物根"——
         对脚手架预建文件天然免疫，不需要逐个列哨兵。
      2. 无快照时退回占位/模板/代码 stub 启发式判定。

    关键约束（回归用）：开工后**删掉**脚手架模板不算产出。
    此前只比较"不相等"，于是清空产物目录也会被计为 1 个产出。
    现在要求当前哈希与开工哈希不同，且产物根仍有真实文件。
    """
    paths = [p.strip() for p in NODES[node].get("artifact", "").split(",") if p.strip()]
    start_snapshot = None
    try:
        state = load_state(root)
        start_snapshot = (state.get("nodes", {}).get(node) or {}).get("start_artifact_hash")
    except (OSError, ValueError, KeyError):
        start_snapshot = None

    current = artifact_snapshot(root, node)
    if isinstance(start_snapshot, dict) and start_snapshot:
        changed = [k for k, v in current.items()
                   if start_snapshot.get(k) != v and _root_has_real_output(root, k)]
        return len(changed)

    total = 0
    for rel_root in paths:
        full_root = os.path.join(root, rel_root)
        if os.path.isfile(full_root):
            if _is_filled(full_root, rel_root):
                total += 1
        elif os.path.isdir(full_root):
            total += _count_real_files(root, full_root)
    return total


def _root_has_real_output(root, rel_root):
    """产物根当前是否仍有真实文件（用于排除"只删不建"的哈希变化）。"""
    full_root = os.path.join(root, rel_root)
    if os.path.isfile(full_root):
        return _is_filled(full_root, rel_root)
    if os.path.isdir(full_root):
        return _count_real_files(root, full_root) > 0
    return False


def _count_real_files(root, full_dir):
    total = 0
    for dp, dns, fns in os.walk(full_dir):
        if ".git" in dp.split(os.sep):
            dns[:] = []
            continue
        for f in fns:
            full = os.path.join(dp, f)
            if _is_filled(full, os.path.relpath(full, root)):
                total += 1
    return total


def _auto_register_outputs(root, node, executor):
    """node-finish 时自动把本节点产物登记进 artifacts-registry（幂等）。

    这样"文件必有入库记录"不再依赖子 Agent 记得手动跑 register-artifact：
    凡是落在节点 artifact 目录内的真实产出，完成节点时自动入账。
    """
    reg_path = os.path.join(root, "state", "reports", "artifacts-registry.json")
    try:
        reg = json.loads(open(reg_path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        reg = {"schema_version": "artifacts-registry/1.0", "artifacts": []}
    items = reg.setdefault("artifacts", [])
    by_path = {a.get("path"): a for a in items}
    paths = [p.strip() for p in NODES[node].get("artifact", "").split(",") if p.strip()]
    added = 0
    for rel_root in paths:
        full_root = os.path.join(root, rel_root)
        candidates = []
        if os.path.isfile(full_root):
            candidates.append((rel_root, full_root))
        elif os.path.isdir(full_root):
            for dp, dns, fns in os.walk(full_root):
                if ".git" in dp.split(os.sep):
                    dns[:] = []
                    continue
                for f in fns:
                    full = os.path.join(dp, f)
                    candidates.append((os.path.relpath(full, root).replace("\\", "/"), full))
        for rel, full in candidates:
            if not _is_filled(full, rel):
                continue
            digest = sha256_of(full)
            prev = by_path.get(rel)
            if prev and prev.get("sha256") == digest:
                continue  # 内容未变，不重复登记
            entry = {
                "path": rel, "node": node, "kind": "auto",
                "sha256": digest, "size": os.path.getsize(full), "is_dir": False,
                "registered_by": executor, "registered_at": now_iso(),
                "note": "node-finish 自动登记",
            }
            if prev:
                entry["previous_sha256"] = prev.get("sha256")
                items[:] = [a for a in items if a.get("path") != rel]
            items.append(entry)
            by_path[rel] = entry
            added += 1
    if added:
        os.makedirs(os.path.dirname(reg_path), exist_ok=True)
        save_json_atomic(reg_path, reg)
        print(f"[state_utils] 已自动登记 {added} 个产物到 state/reports/artifacts-registry.json")


def require_node_deliverables(root, node, allow_empty=False, allow_no_checkpoint=False):
    """节点交付物完整性校验（供 node-finish 与 round-decide / scope-promote 共用）。

    2.0.0 修复 P1-8：迭代节点（N4/N5/N7/N8）的 completed 由 round-decide 直接写，
    从不经过 node-finish，导致 checkpoint 与产物校验对"最需要它的长任务"完全失效。
    把校验抽成函数，任何"把节点标 completed"的路径都必须调用它。
    """
    if node == "N0":
        return
    if not allow_no_checkpoint:
        ckpt = os.path.join(root, "state", "checkpoints", f"{node}.jsonl")
        if not (os.path.isfile(ckpt) and os.path.getsize(ckpt) > 0):
            sys.exit(
                f"[state_utils] 拒绝：节点 {node} 没有任何进度快照（state/checkpoints/{node}.jsonl）。\n"
                f"  分阶段归档是硬要求——每个 Phase 结束应落一次快照，中断后才可续跑：\n"
                f"    python state/state_utils.py checkpoint {node} --phase \"<Phase N>\" "
                f"--done \"<已完成>\" --pending \"<待完成>\" --artifact <产物>\n"
                f"  若该节点确实为单步动作，可加 --allow-no-checkpoint 并说明原因。"
            )
    if not allow_empty:
        if _count_node_outputs(root, node) == 0:
            sys.exit(
                f"[state_utils] 拒绝：节点 {node}（{NODES[node]['name']}）声明的产物目录 "
                f"{NODES[node]['artifact']} 下没有任何实际产出文件。\n"
                f"  禁止「空产物标完成」——请先产出本节点应有的交付物。\n"
                f"  判定口径：空文件、纯空白、脚手架预建模板（未替换占位内容）、"
                f"仍带 NotImplementedError 的代码 stub 都不算产出；"
                f"开工后仅删掉模板同样不算产出。\n"
                f"  先用 node-log 记录进展、checkpoint 落快照，再重跑本命令。"
            )


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
            sys.exit(f"[state_utils] 项目未初始化：{root}\n"
                     f"  请先运行: python state/state_utils.py init --dir {root} --name <竞赛名称>")
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


