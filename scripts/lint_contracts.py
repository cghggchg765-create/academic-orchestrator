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
#
# 口径（2.0.0 academic-orchestrator）：
#   - 学术能力主体（academic-paper / deep-research / academic-paper-reviewer /
#     academic-pipeline）、ARIS、nature-* 家族由各自插件/技能库提供，本插件不持有副本。
#   - 本插件只保留「编排核心 + 数学建模子轨 + 去AI化 + 图表演示/审阅」等原生组件。
#   - 第三方重复副本已于 2.0.0 物理删除（xlsx / frontend-design / theme-factory /
#     test-driven-development / systematic-debugging / receiving-code-review /
#     subagent-driven-development / drawio-skill / make-pdf / investigate），
#     能力需求改由 mm-skill-router 运行时扫描发现，不再打包分发。
# 改这个数字前先确认 skills/ 与 agents/ 实际文件数，并用 lint 反向校验。
EXPECTED_COUNTS = {"skills": 25, "agents": 21, "commands": 7}


def check_component_counts() -> None:
    """数量断言：agents/ 与 skills/ 的实际文件数作为契约（防止文档口径再次漂移）。"""
    agents = [p for p in (ROOT / "agents").glob("*.md")]
    skills = [p for p in (ROOT / "skills").iterdir() if p.is_dir()]
    if len(agents) != EXPECTED_COUNTS["agents"]:
        error(f"agents/ 应为 {EXPECTED_COUNTS['agents']} 个 Agent 定义，实际 {len(agents)}")
    if len(skills) != EXPECTED_COUNTS["skills"]:
        error(f"skills/ 应为 {EXPECTED_COUNTS['skills']} 个 Skill 包，实际 {len(skills)}")


# 用户直接读到的组件口径文案所在文件（归档文档刻意排除：历史记录不改写）
COUNT_DOCS = ("README.md", "能力盘点.md", "commands/mm-help.md")


def check_documented_counts() -> None:
    """文档里写的 "N Agent / M Skill / K 命令" 必须与 EXPECTED_COUNTS 一致。

    回归用：实际 25 个 skill，但 README / 能力盘点 / mm-help 长期写 23，
    lint 只断言目录数量、不比对文案，于是漂移无人发现，用户看到的口径是错的。
    """
    import re as _re
    want = (EXPECTED_COUNTS["agents"], EXPECTED_COUNTS["skills"], EXPECTED_COUNTS["commands"])
    pattern = _re.compile(r"(\d+)\s*Agent\s*/\s*(\d+)\s*Skill\s*/\s*(\d+)\s*命令")
    for rel in COUNT_DOCS:
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            got = tuple(int(match.group(i)) for i in (1, 2, 3))
            if got != want:
                line_no = text[:match.start()].count("\n") + 1
                error(f"{rel}:{line_no} 组件口径写 {got[0]} Agent / {got[1]} Skill / {got[2]} 命令，"
                      f"应为 {want[0]} / {want[1]} / {want[2]}（与 EXPECTED_COUNTS 一致）")


def check_no_big_archives_tracked() -> None:
    """大型压缩包不允许进入 git 跟踪（仓库卫生）。"""
    import subprocess
    r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.lower().endswith((".rar", ".zip", ".7z")) and "templates/" not in line:
            error(f"大型压缩包被 git 跟踪: {line}")


def check_documented_commands_exist() -> None:
    """文档里出现的 `state_utils.py <cmd>` 必须是真实注册的子命令。

    回归用：skills/academic-orchestration 长期写"写入 dispatch.json / corrections.jsonl"，
    却从未点名 CLI 入口——反过来文档也可能写出不存在的命令名（幻觉命令）。
    这里只做"名字存在性"校验（不执行命令，避免副作用与速度问题）。
    """
    import re as _re
    import subprocess as _sp
    help_out = _sp.run([sys.executable, str(ROOT / "shared" / "state-engine" / "state_utils.py"), "--help"],
                       capture_output=True, text=True)
    match = _re.search(r"\{([a-z0-9,\-]+)\}", help_out.stdout or "")
    if not match:
        error("无法解析 state_utils.py 的可用子命令列表")
        return
    real = set(match.group(1).split(","))
    pattern = _re.compile(r"state_utils\.py`?\s+([a-z][a-z0-9-]*)")
    scan = [ROOT / "README.md", ROOT / "能力盘点.md", ROOT / "commands"]
    scan += [ROOT / "skills", ROOT / "agents", ROOT / "docs"]
    for target in scan:
        files = [target] if target.is_file() else [
            p for p in target.rglob("*.md") if ".venv" not in str(p)]
        for path in files:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in pattern.finditer(text):
                cmd = m.group(1)
                if cmd not in real:
                    line_no = text[:m.start()].count("\n") + 1
                    rel = path.relative_to(ROOT)
                    error(f"{rel}:{line_no} 引用了不存在的子命令 `{cmd}`（state_utils.py 无此命令）")

    # 同时校验文档里 `python scripts/<x>.py` 形式的引用是否真实存在。
    # 与命令检查同源动机：文档让用户跑一个不存在的脚本，等于机制不存在。
    #
    # 路径解析有两种合法基准，必须都认，否则会误报：
    #   ① 仓库根：`python scripts/external_isolation.py`（项目级工具）
    #   ② 所在 skill 目录：`python scripts/doctor.py`（该 skill 自带的脚本，
    #      文档里写成相对自身目录的形式，如 skills/figure-pipeline/SKILL.md）
    script_pattern = _re.compile(r"python (scripts/[A-Za-z0-9_\-]+\.py)")
    for target in scan:
        files = [target] if target.is_file() else [
            p for p in target.rglob("*.md") if ".venv" not in str(p)]
        for path in files:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in script_pattern.finditer(text):
                rel_script = m.group(1)
                if (ROOT / rel_script).is_file():
                    continue
                # 基准②：从文档所在目录向上找，看是否有匹配的 scripts/<x>.py
                name = Path(rel_script).name
                found = any((parent / "scripts" / name).is_file()
                            for parent in [path.parent, *path.parent.parents]
                            if parent.is_relative_to(ROOT))
                if found:
                    continue
                line_no = text[:m.start()].count("\n") + 1
                rel = path.relative_to(ROOT)
                error(f"{rel}:{line_no} 引用了不存在的脚本 `{rel_script}`"
                      f"（仓库根与所在 skill 目录下都没有）")


def check_dispatch_agent_names() -> None:
    """文档里 `subagent_type=<name>` 示例必须是真实存在的 Agent。

    回归动机：用户反馈"调用时用的都是通用子 Agent"。排查发现注册链路完整，
    但若文档示例写出不存在的名字，主 Agent 派发失败后会回退 general-purpose
    ——专业分工静默失效。同时把派发示例统一为带插件前缀名
    （`academic-orchestrator:<name>`），裸名在其它插件装了同名 Agent 时会被遮蔽。
    """
    disk_agents = {p.stem for p in (ROOT / "agents").glob("*.md")}
    pattern = re.compile(r"subagent_type[=(]\s*[\"'`]?([A-Za-z][\w:-]*)")
    scan = [ROOT / "README.md", ROOT / "能力盘点.md", ROOT / "commands"]
    scan += [ROOT / "skills", ROOT / "agents", ROOT / "docs"]
    seen = set()
    for target in scan:
        files = [target] if target.is_file() else [
            p for p in target.rglob("*.md") if ".venv" not in str(p)]
        for path in files:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in pattern.finditer(text):
                name = m.group(1)
                if name in ("general-purpose", "Agent", "Task"):
                    continue  # 明确的通用/占位示例
                if name.endswith(":") or "<" in text[m.start():m.end() + 1]:
                    continue  # academic-orchestrator:<executor 名> 是占位符写法，不是字面名
                bare = name.split(":", 1)[-1]
                if bare in disk_agents:
                    continue
                key = (str(path), name)
                if key in seen:
                    continue
                seen.add(key)
                line_no = text[:m.start()].count("\n") + 1
                rel = path.relative_to(ROOT)
                error(f"{rel}:{line_no} 派发示例 `subagent_type={name}` 的 Agent 不存在"
                      f"（agents/ 下没有 {bare}.md）——照抄会派发失败并回退通用 Agent")


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
        # 插件命名空间前缀（academic-orchestrator:xxx）→ 目录名（skills/xxx/）
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
    # 编排协议必须声明完整专业 Agent 集（防"完整流程漏用 Agent"）
    # 2.0.0：编排载体由 agents/orchestrator.md（子 Agent）迁至
    # skills/academic-orchestration/SKILL.md（主 Agent 协议），因宿主禁止子 Agent 嵌套派发。
    orch_path = ROOT / "skills" / "academic-orchestration" / "SKILL.md"
    if not orch_path.exists():
        error("全流程覆盖: 编排协议 skills/academic-orchestration/SKILL.md 缺失")
    else:
        orch = orch_path.read_text(encoding="utf-8")
        for agent in sorted(expected_agents | {"humanize"}):
            if agent not in orch:
                error(f"全流程覆盖: 编排协议未声明可委托 {agent}")
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
            # registry 存插件注册名（`academic-orchestrator:mm-algorithm-dev`），二者等价。
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


def check_gates_registry() -> None:
    """门禁登记单一事实源：shared/contracts/gates-registry.json ↔ state_defs NODES.gates。

    三层比对（缺任一层都会出现"改一处、另一处照旧生效"的双份事实源）：
      ① 门禁 id 集合：登记表 ↔ NODES 使用集合；
      ② 归属节点：登记表每条的 `node` 字段（可逗号分隔，如 B1 = "N6,N7,N8"）
         必须与该门禁在 NODES 里被哪些节点声明完全一致；
      ③ 必要字段齐全。
    ② 此前是个只 strip 不比较的空循环，于是把 B1 的 node 改成 N5 也能 lint 通过。
    """
    reg_path = ROOT / "shared" / "contracts" / "gates-registry.json"
    if not reg_path.exists():
        error("门禁登记表缺失: shared/contracts/gates-registry.json")
        return
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    declared = set()
    declared_nodes: dict[str, set[str]] = {}
    for g in reg.get("gates", []):
        gid = g.get("id")
        if not gid:
            error("门禁登记表存在无 id 的条目")
            continue
        declared.add(gid)
        nodes = {n.strip() for n in str(g.get("node", "")).split(",") if n.strip()}
        if not nodes:
            error(f"门禁 {gid} 未声明归属节点（node 字段为空）")
        declared_nodes[gid] = nodes
        for key in ("timing", "kind", "blocking", "criterion", "producer"):
            if not g.get(key):
                error(f"门禁 {gid} 缺字段 {key}")
    source = ROOT / "shared" / "state-engine" / "state_utils.py"
    spec = importlib.util.spec_from_file_location("mm_state_utils_g", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    used: dict[str, set[str]] = {}
    for node_id, info in module.NODES.items():
        for gate in info.get("gates", []):
            used.setdefault(gate, set()).add(node_id)
    # 迭代动态门禁（S<n>-Nx）不静态登记
    for gate in sorted(set(used) - declared):
        error(f"门禁 {gate} 在 NODES 中被使用但未登记于 gates-registry.json")
    for gate in sorted(declared - set(used)):
        error(f"门禁 {gate} 已登记于 gates-registry.json 但无任何节点使用（孤儿门禁）")
    # 归属节点逐条比对：登记表说属于哪些节点，NODES 就必须在哪些节点声明它
    for gate in sorted(declared & set(used)):
        if declared_nodes.get(gate) != used[gate]:
            error(f"门禁 {gate} 归属节点漂移：gates-registry.json 写 "
                  f"{sorted(declared_nodes.get(gate) or [])}，"
                  f"NODES 实际在 {sorted(used[gate])} 声明")
    # 审阅类门禁的 producer 必须是该节点的合法审阅者（三份事实源：登记表 producer /
    # NODES.reviewer + secondary_reviewers / agents/*.md）。任一处改名而其余未跟，
    # 运行时 node-review 会拒掉"登记表说要它出结论"的那个 Agent。
    #
    # 匹配必须按整词，不能按子串：'reviewer' 是 'mm-viz-reviewer' 的子串，
    # 子串匹配会让把 W2 的 producer 写成 mm-viz-reviewer 也通过。
    for g in reg.get("gates", []):
        if g.get("kind") != "review" or not g.get("id"):
            continue
        producer_tokens = {t for t in re.split(r"[+\s,]+", str(g.get("producer") or "")) if t}
        for node_id in declared_nodes.get(g["id"], set()):
            allowed = set(module.expected_reviewers(node_id)) if node_id in module.NODES else set()
            if allowed and not (allowed & producer_tokens):
                error(f"门禁 {g['id']} 的 producer「{g.get('producer')}」不是节点 {node_id} 的合法审阅者"
                      f"（NODES 允许 {sorted(allowed)}）——登记表与节点定义漂移")


def check_mcp_requirement_contract() -> None:
    """MCP 必调表结构契约（防"说明文字与机器判定各写一份"）。

    NODES 里没有 mcp_required 字段，因此"哪些节点必须调 MCP"只能由
    state_defs.MCP_MANDATORY_NODES 这一张表定义。该表必须满足：
      ① 每个条目同时带人类可读 desc 与机器判定用的 all/any token 组；
      ② all 与 any 不能同时为空（否则任何留痕都能满足 = 门禁形同摆设）；
      ③ 键必须是 NODES 里的真实节点。
    此前 desc 与 token 组是两张分开维护的表，改一处就会让"报错说要 paper-mcp、
    实际校验查别的"，而且任何一条都能被静默漏掉。
    """
    source = ROOT / "shared" / "state-engine" / "state_utils.py"
    spec = importlib.util.spec_from_file_location("mm_state_utils_mcp", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    table = getattr(module, "MCP_MANDATORY_NODES", None)
    if not isinstance(table, dict):
        error("state_defs.MCP_MANDATORY_NODES 缺失或不是 dict")
        return
    for node, entry in table.items():
        if node not in module.NODES:
            error(f"MCP 必调表含未知节点 {node}")
            continue
        if not isinstance(entry, dict):
            error(f"MCP 必调表 {node} 必须是 dict（含 desc/all/any）")
            continue
        if not str(entry.get("desc") or "").strip():
            error(f"MCP 必调表 {node} 缺 desc（报错信息无法说明该调什么）")
        has_all, has_any = set(entry.get("all") or ()), set(entry.get("any") or ())
        if not has_all and not has_any:
            error(f"MCP 必调表 {node} 的 all/any 全为空——任何检索留痕都能满足门禁")
    # 迭代节点的 MCP 门禁必须每轮生效，否则"纯内生输出"可跨轮复用旧留痕
    for node in ("N4", "N5", "N7"):
        if node not in table:
            error(f"迭代节点 {node} 未列入 MCP 必调表（每轮必须重新检索）")


def check_benchmark_contract() -> None:
    """图表对标契约：B1 门禁必须有专职审阅 Agent + 对标 skill + 矩阵 schema 三者齐备。"""
    b1_agents = [p for p in (ROOT / "agents").glob("*.md") if "mm-figure-table-benchmarker" in p.name]
    if not b1_agents:
        error("B1 门禁缺少专职审阅 Agent: agents/mm-figure-table-benchmarker.md")
    if not (ROOT / "skills" / "figure-table-benchmark" / "SKILL.md").exists():
        error("B1 门禁缺少对标规范 skill: skills/figure-table-benchmark/SKILL.md")
    if not (ROOT / "skills" / "figure-table-benchmark" / "references" / "benchmark-matrix.schema.json").exists():
        error("B1 门禁缺少矩阵 schema: skills/figure-table-benchmark/references/benchmark-matrix.schema.json")
    reg = json.loads((ROOT / "shared" / "contracts" / "gates-registry.json").read_text(encoding="utf-8"))
    b1 = [g for g in reg.get("gates", []) if g.get("id") == "B1"]
    if not b1:
        error("B1 门禁未登记于 gates-registry.json")
    elif "mm-figure-table-benchmarker" not in b1[0].get("producer", ""):
        error("B1 门禁的 producer 必须为 mm-figure-table-benchmarker")


def check_data_lineage_contract() -> None:
    """数据处理交叉检验契约（2.0.0）：
    ① 血缘 schema 必须存在；
    ② 血缘校验器必须存在且可导入；
    ③ D1 门禁必须声明血缘要求（否则 D1 退回"只看 CSV 可读"）；
    ④ dataprep agent 必须声明血缘与分阶段归档要求（否则执行方不知道要做）；
    ⑤ 编排协议必须声明 G.1-G.4（否则派发时不带要求）。
    """
    schema = ROOT / "shared" / "contracts" / "math_modeling" / "data_lineage.schema.json"
    if not schema.exists():
        error("数据血缘 schema 缺失: shared/contracts/math_modeling/data_lineage.schema.json")
    validator = ROOT / "scripts" / "validate_data_lineage.py"
    if not validator.exists():
        error("数据血缘校验器缺失: scripts/validate_data_lineage.py")
    # D1 必须含血缘要求
    greg = ROOT / "shared" / "contracts" / "gates-registry.json"
    if greg.exists():
        gates = json.loads(greg.read_text(encoding="utf-8")).get("gates", [])
        d1 = [g for g in gates if g.get("id") == "D1"]
        if not d1:
            error("D1 门禁未登记")
        else:
            crit = d1[0].get("criterion", "")
            if "血缘" not in crit:
                error("D1 门禁未声明数据血缘要求（处理过程无法交叉检验）")
            th = d1[0].get("thresholds") or {}
            if not th.get("require_raw_hash"):
                error("D1 门禁 thresholds 缺 require_raw_hash（raw 只读性未强制）")
    # dataprep 必须声明血缘 + 归档
    dp = ROOT / "agents" / "dataprep.md"
    if dp.exists():
        text = dp.read_text(encoding="utf-8", errors="ignore")
        for kw, why in (("validate_data_lineage", "血缘校验"), ("checkpoint", "分阶段归档"),
                        ("register-artifact", "产物入库登记")):
            if kw not in text:
                error(f"agents/dataprep.md 未声明 {why}（{kw}）")
    # D1 判据三处一致（gates-registry / mm-iteration-engine SKILL / reviewer）：
    # 任一处缺"血缘"就会让执行方或审阅方不知道要做，必须 lint 拦住漂移。
    d1_sources = [
        (ROOT / "skills" / "mm-iteration-engine" / "SKILL.md", "mm-iteration-engine §6.3 门禁表"),
        (ROOT / "agents" / "reviewer.md", "reviewer N2 审阅清单"),
        (ROOT / "skills" / "mm-data-preprocessing" / "SKILL.md", "mm-data-preprocessing 产出物规范"),
    ]
    for path, label in d1_sources:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "血缘" not in text:
            error(f"D1 判据漂移：{label} 未提及数据血缘（{path.relative_to(ROOT)}）")
    # 编排协议必须声明 G.1-G.4
    orch = ROOT / "skills" / "academic-orchestration" / "SKILL.md"
    if orch.exists():
        text = orch.read_text(encoding="utf-8", errors="ignore")
        for anchor in ("### G. 分阶段归档与入库记录", "checkpoint", "register-artifact", "orphan-scan"):
            if anchor not in text:
                error(f"academic-orchestration 未声明分阶段归档/入库要求: 缺 {anchor}")


DELETED_THIRD_PARTY_SKILLS = (
    "xlsx", "frontend-design", "theme-factory", "test-driven-development",
    "systematic-debugging", "receiving-code-review", "subagent-driven-development",
    "drawio-skill", "make-pdf", "investigate",
)


def check_no_deleted_skill_loads() -> None:
    """禁止对已删除的第三方 skill 写 skill() 加载语句（2.0.0 去重后防回归）。

    这些 skill 已在 2.0.0 物理删除，改由 mm-skill-router 运行时发现。
    文档里若仍写 skill("xlsx") 之类，运行时会加载失败。
    允许"提到名字"（如说明该能力由外部插件提供），但不允许 skill("<name>") 的加载调用。
    """
    targets = list((ROOT / "agents").glob("*.md")) + \
              list((ROOT / "skills").glob("*/SKILL.md")) + \
              list((ROOT / "commands").glob("*.md"))
    for path in targets:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in DELETED_THIRD_PARTY_SKILLS:
            for pat in (f'skill("{name}")', f"skill('{name}')"):
                if pat in text:
                    error(f"已删除 skill 的加载语句残留: {path.relative_to(ROOT)} 含 {pat}"
                          f"（应改为运行时按需路由或指向外部插件）")


SKILL_FRONTMATTER_KEYS = {"name", "description", "when_to_use", "license", "metadata"}
AGENT_FRONTMATTER_KEYS = {
    "name", "description", "tools", "disallowedTools", "skills", "mcpServers",
    "model", "thoughtLevel", "permissionMode", "maxTurns", "background",
    "injectAgentsMd", "memory", "color",
}


def check_frontmatter_whitelist() -> None:
    """frontmatter 白名单硬校验（2.0.0）。

    ZCode 宿主规则：
      - skill 含白名单外的顶层键 → 仍然加载，但 safeToAutoLoad=false（不会被自动加载）
      - agent 含任何非 strict 键 → 整个 agent 解析失败、不注册
    两者都是静默失败，必须由 lint 拦住。
    """
    for d in sorted((ROOT / "skills").iterdir()):
        if not d.is_dir():
            continue
        p = d / "SKILL.md"
        if not p.exists():
            continue
        data = _load_frontmatter(p)
        if data is None:
            continue
        extra = sorted(set(data) - SKILL_FRONTMATTER_KEYS)
        if extra:
            error(f"skill {d.name} 含非白名单 frontmatter 键 {extra}"
                  f"（会被判 safeToAutoLoad=false，不被自动加载）")
        desc = data.get("description")
        if isinstance(desc, str) and len(desc) > 1024:
            error(f"skill {d.name} 的 description 超 1024 字符（{len(desc)}）→ 整个 skill 被丢弃")
    for p in sorted((ROOT / "agents").glob("*.md")):
        data = _load_frontmatter(p)
        if data is None:
            continue
        extra = sorted(set(data) - AGENT_FRONTMATTER_KEYS)
        if extra:
            error(f"agent {p.stem} 含非官方 frontmatter 键 {extra}（strict schema，整个 agent 不会注册）")


def main() -> int:
    scan_markdown()
    check_registry()
    check_registry_vs_nodes()
    check_frontmatter()
    check_frontmatter_whitelist()
    check_version_alignment()
    check_component_counts()
    check_documented_counts()
    check_documented_commands_exist()
    check_dispatch_agent_names()
    check_no_big_archives_tracked()
    check_naming_redlines()
    check_plugin_manifest()
    check_latex_scaffold()
    check_full_pipeline_coverage()
    check_all_components_referenced()
    check_agent_boundaries()
    check_professional_skill_contract()
    check_gates_registry()
    check_benchmark_contract()
    check_mcp_requirement_contract()
    check_data_lineage_contract()
    check_no_deleted_skill_loads()
    check_user_level_sync()
    if ERRORS:
        print("契约检查失败:")
        print("\n".join(f"- {item}" for item in ERRORS))
        return 1
    print("契约检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
