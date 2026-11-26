#!/usr/bin/env python3
"""仓库级契约检查：路径、命令、注册节点、frontmatter、版本与 LaTeX 结构。

新增检查项（v1.2.0）：
- NODES 定义与 registry.json 双份一致（executor/reviewer/skills/gates/artifact/upstream）
- SKILL.md frontmatter 必填（name/description）
- 版本单一来源：pyproject.toml == state_utils 脚手架 skill_version == 主控/迭代引擎 SKILL 版本
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []


def error(message: str) -> None:
    ERRORS.append(message)


def scan_markdown() -> None:
    patterns = {
        r"python python state/state_utils\.py": "重复 python 命令",
        r"Word_Version|LaTeX_Version": "旧论文目录命名",
        r"state/nodes/N[0-8]-": "状态节点物理目录仍带序号",
    }
    for path in ROOT.rglob("*.md"):
        if any(part in {".git", ".zcode", ".agents", ".venv", "venv"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in patterns.items():
            if re.search(pattern, text):
                error(f"{label}: {path.relative_to(ROOT)}")


def check_registry() -> None:
    path = ROOT / "shared" / "state-engine" / "registry.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    ids = {f"N{i}" for i in range(1, 9)}
    actual = {entry.get("id") for entry in doc.get("nodes", [])}
    if actual != ids:
        error(f"registry 节点不完整: {sorted(actual)}")
    for entry in doc.get("nodes", []):
        homepage = entry.get("homepage", "")
        if re.search(r"nodes/N[0-8]-", homepage):
            error(f"registry homepage 使用序号物理目录: {entry.get('id')}")
        if "Word" in entry.get("artifact_dir", "") or "LaTeX_Version" in entry.get("artifact_dir", ""):
            error(f"registry 使用旧论文目录: {entry.get('id')}")


def check_registry_vs_nodes() -> None:
    """state_utils.py 的 NODES/UPSTREAM 与 shared/state-engine/registry.json 必须双份一致。"""
    source = ROOT / "shared" / "state-engine" / "state_utils.py"
    spec = importlib.util.spec_from_file_location("mm_state_utils", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    registry = json.loads((ROOT / "shared" / "state-engine" / "registry.json").read_text(encoding="utf-8"))
    by_id = {entry.get("id"): entry for entry in registry.get("nodes", [])}
    for node_id, entry in by_id.items():
        info = module.NODES.get(node_id)
        if info is None:
            error(f"registry 节点 {node_id} 在 NODES 中不存在")
            continue
        if entry.get("executor") != info.get("executor"):
            error(f"节点 {node_id} executor 不一致: registry={entry.get('executor')}, NODES={info.get('executor')}")
        if entry.get("reviewer") != info.get("reviewer"):
            error(f"节点 {node_id} reviewer 不一致: registry={entry.get('reviewer')}, NODES={info.get('reviewer')}")
        if module.normalized_skill_set(entry.get("required_skills", [])) != module.normalized_skill_set(info.get("skills", [])):
            error(f"节点 {node_id} skills 不一致")
        if sorted(entry.get("gates", [])) != sorted(info.get("gates", [])):
            error(f"节点 {node_id} gates 不一致")
        if entry.get("artifact_dir") != info.get("artifact"):
            error(f"节点 {node_id} artifact 不一致: registry={entry.get('artifact_dir')}, NODES={info.get('artifact')}")
        expected_up = [up for up, _ in module.UPSTREAM.get(node_id, [])]
        if sorted(entry.get("upstream", [])) != sorted(expected_up):
            error(f"节点 {node_id} upstream 不一致: registry={entry.get('upstream')}, NODES={expected_up}")


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate frontmatter keys."""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_frontmatter(path: Path) -> dict | None:
    """Parse one Markdown frontmatter block as a YAML mapping."""
    rel = path.relative_to(ROOT)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines or lines[0].strip() != "---":
        error(f"frontmatter 缺失或格式错误: {rel}")
        return None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        error(f"frontmatter 未闭合: {rel}")
        return None
    raw = "\n".join(lines[1:end])
    try:
        data = yaml.load(raw, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        error(f"frontmatter YAML 无效: {rel}: {exc}")
        return None
    if not isinstance(data, dict):
        error(f"frontmatter YAML 必须是映射: {rel}")
        return None
    return data


def check_frontmatter() -> None:
    component_files = [
        *((ROOT / "skills").glob("*/SKILL.md")),
        *((ROOT / "agents").glob("*.md")),
        *((ROOT / "commands").glob("*.md")),
    ]
    for path in sorted(component_files):
        data = _load_frontmatter(path)
        if data is None:
            continue
        rel = path.relative_to(ROOT)
        for key in ("name", "description"):
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                error(f"frontmatter 缺少或无效 {key}: {rel}")


def check_version_alignment() -> None:
    pyproject = ROOT / "pyproject.toml"
    m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
    version = m.group(1) if m else None
    if not version:
        error("pyproject.toml 缺少 version")
        return
    state_utils_srcs = [
        ROOT / "shared" / "state-engine" / "state_scaffold.py",
        ROOT / "shared" / "state-engine" / "state_utils.py",
    ]
    state_utils = "".join(p.read_text(encoding="utf-8") for p in state_utils_srcs)
    if f'"skill_version": "{version}"' not in state_utils:
        error(f"state_utils 脚手架 skill_version 与 pyproject({version}) 不一致")
    for skill_file in ("skills/mm-iteration-engine/SKILL.md", "skills/mathematical-modeling/SKILL.md"):
        text = (ROOT / skill_file).read_text(encoding="utf-8")
        if not re.search(rf'version:\s*"{version}"', text):
            error(f"{skill_file} 版本与 pyproject({version}) 不一致")
    template = ROOT / "skills" / "mm-iteration-engine" / "templates" / "state" / "decision_log.json"
    if f'"skill_version": "{version}"' not in template.read_text(encoding="utf-8"):
        error(f"templates/state/decision_log.json 的 skill_version 与 pyproject({version}) 不一致")


# 组件计数单一来源（skills/agents/commands 的契约数量）。
# ARS 学术四技能与 16 个 /ars-* 命令已移交 academic-research-skills 插件单独分发，
# 本插件不再持有副本，因此计数按本插件实际分发包计算。
EXPECTED_COUNTS = {"skills": 30, "agents": 24, "commands": 6}


def check_component_counts() -> None:
    """数量断言：agents/ 与 skills/ 的实际文件数作为契约（防止文档口径再次漂移）。"""
    agents = [p for p in (ROOT / "agents").glob("*.md")]
    skills = [p for p in (ROOT / "skills").iterdir() if p.is_dir()]
    if len(agents) != EXPECTED_COUNTS["agents"]:
        error(f"agents/ 应为 {EXPECTED_COUNTS['agents']} 个 Agent 定义，实际 {len(agents)}")
    if len(skills) != EXPECTED_COUNTS["skills"]:
        error(f"skills/ 应为 {EXPECTED_COUNTS['skills']} 个 Skill 包，实际 {len(skills)}")


def check_no_big_archives_tracked() -> None:
    """大型压缩包不允许进入 git 跟踪（仓库卫生）。"""
    import subprocess
    r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.lower().endswith((".rar", ".zip", ".7z")) and "templates/" not in line:
            error(f"大型压缩包被 git 跟踪: {line}")


def check_naming_redlines() -> None:
    """命名红线（回归防护）：状态目录必须为 state；标准文件名不允许下划线或数字前缀。

    只检查"文件名/路径形态"的旧名（带后缀或作为目录段），不检查裸单词，
    避免误伤代码标识符（append_version_update）与协议枚举（error_analysis_failure）。
    """
    banned = [
        "00_State", "Data_Log.md", "Team_Info.txt", "Key_Requirements.md",
        "Problem_Notes.md", "README_Code.md", "README_LATEX.md", "README_提交说明.txt",
        "README_项目总说明.md", "bug_fix_log.md", "daily_log.md", "version_update.md",
        "model_framework.md", "reference_list.md", "sensitivity_analysis.md",
        "error_analysis.md", "model_validation.md", "defense_script.md",
        "figure_list.md", "draft_backup", "mid_backup", "final_backup",
        "draftbackup", "midbackup", "finalbackup", "showfigures", "show_figures",
        "01_Problem", "02_Data", "03_Code", "04_Result", "05_Report",
        "06_Model", "07_Submission", "08_Material", "09_Log", "10_Backup", "11_Defense",
    ]
    suffixes = {".md", ".py", ".json", ".yml", ".yaml", ".txt", ".tex", ".toml"}
    # These directories are user-provided working materials, not plugin
    # distribution assets. Scanning them makes repository self-checks unstable
    # when a user stores legacy paper outputs beside the checkout.
    excluded_roots = {".git", ".zcode", ".agents", ".venv", "venv", "smoke_iteration",
                      "学习材料", "Material"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if any(part in excluded_roots for part in path.parts):
            continue
        if path.name == "lint_contracts.py":
            continue  # 本文件包含 banned 清单自身
        if path.name == "CHANGELOG.md":
            continue  # 变更记录需保留旧名→新名映射
        if path.name == "legacy_names.py":
            continue  # 旧名迁移映射（升级自愈专用，必须保留旧名）
        if path.name == "self_check.py":
            continue  # 检查用户级旧名残留需引用旧名
        if path.name.startswith("test_") and path.suffix == ".py":
            continue  # 测试断言"旧名不应存在"需引用旧名
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in banned:
            if token in text:
                error(f"命名红线命中（{token}）: {path.relative_to(ROOT)}")


def check_plugin_manifest() -> None:
    """插件打包契约：三个兼容清单一致，声明的组件目录存在且计数匹配，命令 frontmatter 合规。"""
    manifests = [ROOT / ".zcode-plugin/plugin.json", ROOT / ".claude-plugin/plugin.json", ROOT / ".codex-plugin/plugin.json"]
    contents = [p.read_text(encoding="utf-8") for p in manifests if p.exists()]
    if len(contents) != 3:
        error("插件清单缺失（需要 .zcode-plugin/.claude-plugin/.codex-plugin 三个 plugin.json）")
        return
    if len(set(contents)) != 1:
        error("三个 plugin.json 内容不一致")
        return
    manifest = json.loads(contents[0])
    for comp, expected in EXPECTED_COUNTS.items():
        declared = manifest.get(comp, [])
        target = ROOT / comp
        if comp not in manifest:
            error(f"plugin.json 缺少组件声明: {comp}")
            continue
        if not target.is_dir():
            error(f"插件声明的组件目录缺失: {comp}/")
            continue
        count = len([p for p in target.iterdir() if p.is_dir()]) if comp == "skills" else len(list(target.glob("*.md")))
        if count != expected:
            error(f"插件组件 {comp}/ 计数 {count} != 期望 {expected}")
    for p in sorted((ROOT / "commands").glob("*.md")):
        head = p.read_text(encoding="utf-8").split("---\n", 2)
        if len(head) < 2 or not re.search(r"^description:", head[1], re.MULTILINE):
            error(f"命令 frontmatter 缺 description: commands/{p.name}")


def check_latex_scaffold() -> None:
    source = ROOT / "shared" / "state-engine" / "state_scaffold.py"
    text = source.read_text(encoding="utf-8")
    required = ["ReportPaper/LaTeX/main.tex", "ReportPaper/LaTeX/preamble.tex", "ReportPaper/LaTeX/ref.bib"]
    for value in required:
        if value not in text:
            error(f"LaTeX 初始化缺少: {value}")
    if "ReportPaper/Word_Version" in text or "ReportPaper/LaTeX_Version" in text:
        error("初始化脚本仍包含 Word 或 LaTeX_Version")


def check_full_pipeline_coverage() -> None:
    """全流程覆盖契约：NODES 的 executor/reviewer/required_skills 必须存在对应 Agent 文件与 Skill 包；
    数学建模完整流程必须覆盖全部专业 Agent（8 执行 + 2 专用审阅 + humanize 去AI化），且 orchestrator 文档声明了该委托集。"""
    source = ROOT / "shared" / "state-engine" / "state_utils.py"
    spec = importlib.util.spec_from_file_location("mm_state_utils_cov", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    agent_files = {p.stem for p in (ROOT / "agents").glob("*.md")}
    skill_dirs = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}
    expected_agents, expected_skills = set(), set()
    for node_id, info in module.NODES.items():
        if node_id == "N0":
            continue
        expected_agents.add(info["executor"])
        if info.get("reviewer"):
            expected_agents.add(info["reviewer"])
        for skill in info.get("skills", []):
            expected_skills.add(skill)
    for agent in sorted(expected_agents):
        if agent not in agent_files:
            error(f"全流程覆盖: 节点执行/审阅 Agent {agent} 无对应 agents/{agent}.md")
    for skill in sorted(expected_skills):
        # 插件命名空间前缀（math-modeling-agent-system:xxx）→ 目录名（skills/xxx/）
        base = skill.split(":", 1)[-1] if ":" in skill else skill
        if base not in skill_dirs:
            error(f"全流程覆盖: 必读 Skill {skill} 无对应 skills/{base}/")
    # 去 AI 化专项组件
    for comp in ("humanize",):
        if comp not in agent_files:
            error(f"全流程覆盖: 去AI化 Agent {comp} 无对应 agents/{comp}.md")
    for skill in ("humanizer", "academic-humanize"):
        if skill not in skill_dirs:
            error(f"全流程覆盖: 去AI化 Skill {skill} 无对应 skills/{skill}/")
    # orchestrator 委托文档必须声明完整专业 Agent 集（防"完整流程漏用 Agent"）
    orch = (ROOT / "agents" / "orchestrator.md").read_text(encoding="utf-8")
    for agent in sorted(expected_agents | {"humanize"}):
        if agent not in orch:
            error(f"全流程覆盖: orchestrator 文档未声明可委托 {agent}")
    # 主控 SKILL 全流程覆盖表必须含 humanize（去AI化环节已接入流程）
    master = (ROOT / "skills" / "mathematical-modeling" / "SKILL.md").read_text(encoding="utf-8")
    if "humanize" not in master:
        error("全流程覆盖: 主控 SKILL 未声明 humanize 去AI化环节")


def check_all_components_referenced() -> None:
    """全组件引用契约：agents/ 与 skills/ 的全部组件必须在系统内被引用（编排器/主控 SKILL/其他 Agent/命令/文档）。
    自身文件不算引用——防止"完整流程理论覆盖不到"的孤儿组件（全局跑一遍应能调用到所有 Agent 与 skill）。"""
    agents = sorted(p.stem for p in (ROOT / "agents").glob("*.md"))
    skills = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
    sources = (
        [(ROOT / "agents" / f"{a}.md") for a in agents]
        + [(ROOT / "skills" / s / "SKILL.md") for s in skills]
        + list((ROOT / "commands").glob("*.md"))
        + [ROOT / "README.md", ROOT / "pyproject.toml"]
        + list((ROOT / "docs").glob("*.md"))
        + list((ROOT / "scripts").glob("*.py"))
    )

    def referenced(name: str, self_paths) -> int:
        count = 0
        for p in sources:
            if p in self_paths or not p.exists():
                continue
            if name in p.read_text(encoding="utf-8", errors="ignore"):
                count += 1
        return count

    for agent in agents:
        if referenced(agent, {ROOT / "agents" / f"{agent}.md"}) == 0:
            error(f"全组件引用: Agent {agent} 无系统内引用（孤儿组件，完整流程调用不到）")
    for skill in skills:
        if referenced(skill, {ROOT / "skills" / skill / "SKILL.md"}) == 0:
            error(f"全组件引用: Skill {skill} 无系统内引用（孤儿组件，完整流程调用不到）")


def check_agent_boundaries() -> None:
    """职责边界契约（任务-职能匹配防错位）：
    ① 执行 Agent 文件必须引用其负责节点（节点 ID 或名称）——防"Agent 不知道自己是哪个节点的执行者"；
    ② 重叠区 Agent 必须互相声明边界（互引对方职责归属）——防"任务同时可归多个 Agent 时职能划分不清"；
    ③ 每个 Agent 必须有边界声明（MUST NOT / 你不做 / Phase Boundary / 边界）。"""
    source = ROOT / "shared" / "state-engine" / "state_utils.py"
    spec = importlib.util.spec_from_file_location("mm_state_utils_b", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    agents_dir = ROOT / "agents"
    # ① 执行 Agent 引用其负责节点
    for node_id, info in module.NODES.items():
        if node_id == "N0":
            continue
        text = (agents_dir / f"{info['executor']}.md").read_text(encoding="utf-8", errors="ignore")
        if node_id not in text and info["name"].split("/")[0] not in text and info["dir"] not in text:
            error(f"职责边界: 执行 Agent {info['executor']} 未引用其负责节点 {node_id}")
    # ② 重叠区互引
    pairs = [("execute", "coder"), ("analyze", "tuner"), ("typesetting", "latex_linter"),
             ("design", "modeler"), ("polish", "humanize"),
             ("mm-code-reviewer", "reviewer"), ("mm-viz-reviewer", "reviewer")]
    for a, b in pairs:
        ta = (agents_dir / f"{a}.md").read_text(encoding="utf-8", errors="ignore")
        tb = (agents_dir / f"{b}.md").read_text(encoding="utf-8", errors="ignore")
        if b not in ta or a not in tb:
            error(f"职责边界: 重叠区 {a} ↔ {b} 未互相声明边界（必须互相引用对方职责归属，防职能划分不清）")
    # ③ 边界声明
    for f in sorted(agents_dir.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        if not any(k in text for k in ("MUST NOT", "你 MUST NOT", "你不做", "Phase Boundary", "边界")):
            error(f"职责边界: agents/{f.stem}.md 缺少边界声明（MUST NOT / 你不做 / Phase Boundary）")


def check_professional_skill_contract() -> None:
    """专业任务-专业 Agent-专业 skill 三角绑定契约：
    每个节点的 required_skills 中每个 skill，必须在其执行 Agent 文件与审阅 Agent 文件中被引用
    （skill("xxx") 加载指令/声明）——防止"派了专业子 Agent 却没让它调对应专业 skill"。"""
    source = ROOT / "shared" / "state-engine" / "state_utils.py"
    spec = importlib.util.spec_from_file_location("mm_state_utils_ps", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for node_id, info in module.NODES.items():
        if node_id == "N0":
            continue
        for role in ("executor", "reviewer"):
            agent = info.get(role)
            if not agent:
                continue
            text = (ROOT / "agents" / f"{agent}.md").read_text(encoding="utf-8", errors="ignore")
            # 归一化比较：Agent 文件内按裸名引用（`skill("mm-algorithm-dev")`），
            # registry 存插件注册名（`math-modeling-agent-system:mm-algorithm-dev`），二者等价。
            missing = [s for s in info.get("skills", []) if module.skill_basename(s) not in text]
            if missing:
                error(f"专业 skill 契约: {node_id} 的 {role} {agent} 未引用必读 skill {missing}（必须加载并声明）")


def check_user_level_sync() -> None:
    """运行时组件一致性门禁（用户级目录 vs 插件源）。

    ZCode 加载机制：流程中无前缀引用（skill()/registry/subagent_type）命中用户级目录，
    插件组件以 `插件名:组件名` 前缀注册——用户级旧版会导致"实际执行与插件内容断层"。

    两种模式（由仓库根 `.plugin-only` 标志决定）：
    - 同步模式（无标志）：用户级存在本仓库组件副本时，必须与仓库（插件同源）一致；
    - 插件独占模式（有 `.plugin-only`）：用户级**不得存在**本仓库组件（流程已全部用插件前缀名
      引用，用户级副本只会造成遮蔽/双份混乱）。
    无用户级目录的环境（CI 等）跳过。"""
    import importlib.util as _iu
    script = ROOT / "scripts" / "sync_user_level.py"
    spec = _iu.spec_from_file_location("sync_user_level", script)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not (mod.USER / "skills").exists():
        return  # 无用户级副本环境（CI 等）跳过
    plugin_only = (ROOT / ".plugin-only").exists()
    if plugin_only:
        skills, agents, commands = mod.components()
        stray = []
        for user_root in (mod.USER, Path.home() / ".agents"):
            for s in skills:
                installed = {p.name.casefold() for p in (user_root / "skills").iterdir()} if (user_root / "skills").is_dir() else set()
                if s.casefold() in installed:
                    stray.append(f"{user_root.name}:skill:{s}")
            for a in agents:
                installed = {p.stem.casefold() for p in (user_root / "agents").glob("*.md")} if (user_root / "agents").is_dir() else set()
                if a.casefold() in installed:
                    stray.append(f"{user_root.name}:agent:{a}")
            for c in commands:
                installed = {p.stem.casefold() for p in (user_root / "commands").glob("*.md")} if (user_root / "commands").is_dir() else set()
                if c.casefold() in installed:
                    stray.append(f"{user_root.name}:command:{c}")
        if stray:
            error("插件独占模式：用户级目录不得存在本仓库组件副本（请运行 "
                  "`python scripts/sync_user_level.py --plugin-only` 清理）: " + ", ".join(stray[:25]))
        return
    for issue in mod.diff_report():
        error(f"用户级副本与插件同源不一致: {issue}")


def main() -> int:
    scan_markdown()
    check_registry()
    check_registry_vs_nodes()
    check_frontmatter()
    check_version_alignment()
    check_component_counts()
    check_no_big_archives_tracked()
    check_naming_redlines()
    check_plugin_manifest()
    check_latex_scaffold()
    check_full_pipeline_coverage()
    check_all_components_referenced()
    check_agent_boundaries()
    check_professional_skill_contract()
    check_user_level_sync()
    if ERRORS:
        print("契约检查失败:")
        print("\n".join(f"- {item}" for item in ERRORS))
        return 1
    print("契约检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
