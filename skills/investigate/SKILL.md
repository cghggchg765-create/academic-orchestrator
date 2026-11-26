---
name: investigate
preamble-tier: 2
version: 1.0.0
description: |
  Systematic debugging with root cause investigation. Four phases: investigate,
  analyze, hypothesize, implement. Iron Law: no fixes without root cause.
  Use when asked to "debug this", "fix this bug", "why is this broken",
  "investigate this error", or "root cause analysis".
  Proactively invoke this skill (do NOT debug directly) when the user reports
  errors, 500 errors, stack traces, unexpected behavior, "it was working
  yesterday", or is troubleshooting why something stopped working.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - AskUserQuestion
  - WebSearch
triggers:
  - debug this
  - fix this bug
  - why is this broken
  - root cause analysis
  - investigate this error
---

> 维护说明：本文件是 investigate 的权威来源（上游 SKILL.md.tmpl 生成工具未随本插件分发，原 "AUTO-GENERATED" 标记已失效，改为手工维护）。上游 gstack 运行时（`~/.claude/skills/gstack/` 二进制、gbrain、freeze hook）未随本插件分发，相关机械层已剥离；学习记录（learmings）等能力在不具备 gstack 时按下方说明降级。

# Systematic Debugging

## Iron Law

**NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.**

Fixing symptoms creates whack-a-mole debugging. Every fix that doesn't
address root cause makes the next bug harder to find. Find the root cause,
then fix it.

---

## Phase 1: Root Cause Investigation

Gather context before forming any hypothesis.

1. **Collect symptoms:** Read the error messages, stack traces, and reproduction
   steps. If the user hasn't provided enough context, ask ONE question at a
   time via AskUserQuestion.

2. **Read the code:** Trace the code path from the symptom back to potential
   causes. Use Grep to find all references, Read to understand the logic.

3. **Check recent changes:**
   ```bash
   git log --oneline -20 -- <affected-files>
   ```
   Was this working before? What changed? A regression means the root cause
   is in the diff.

4. **Reproduce:** Can you trigger the bug deterministically? If not, gather
   more evidence before proceeding.

5. **Check investigation history:** Search prior learnings for investigations
   on the same files (见下方 "Prior Learnings" 降级说明). Recurring bugs in
   the same area are an architectural smell — note patterns and check whether
   the root cause was structural.

## Prior Learnings

本插件不内置 gstack 学习库；历史学习检索降级为：
- 仓库内检索：`git log --oneline -- <affected-files>` 的同类修复记录；
- 结构化检索：`grep -ril "learnings\|investigation" docs/ skills/<相关模块>/` 查找既往记录；
- 有 gstack 环境的机器可自行运行 `gstack-learnings-search`（非本插件承诺能力）。

若找到既往记录，将其纳入分析。输出：
**"Root cause hypothesis: ..."** —— 针对"哪里错了、为什么错"的具体可检验声明。

---

## Scope Lock

After forming your root cause hypothesis, lock edits to the affected module
to prevent scope creep:

```bash
[ -x "${CLAUDE_SKILL_DIR}/../freeze/bin/check-freeze.sh" ] && echo "FREEZE_AVAILABLE" || echo "FREEZE_UNAVAILABLE"
```

- **FREEZE_AVAILABLE**（宿主环境自带 freeze skill 时）: 将最窄受影响目录写入 freeze 状态文件，告诉用户调试会话的编辑范围已锁定，`/unfreeze` 解除。
- **FREEZE_UNAVAILABLE**: 跳过范围锁定，编辑不受限。若缺陷横跨全仓库或范围确实不清，同样跳过并说明原因。

---

## Phase 2: Pattern Analysis

Check if this bug matches a known pattern:

| Pattern | Signature | Where to look |
|---------|-----------|---------------|
| Race condition | Intermittent, timing-dependent | Concurrent access to shared state |
| Nil/null propagation | NoMethodError, TypeError | Missing guards on optional values |
| State corruption | Inconsistent data, partial updates | Transactions, callbacks, hooks |
| Integration failure | Timeout, unexpected response | External API calls, service boundaries |
| Configuration drift | Works locally, fails in staging/prod | Env vars, feature flags, DB state |
| Stale cache | Shows old data, fixes on cache clear | Redis, CDN, browser cache, Turbo |

Also check:
- `TODOS.md` / 仓库已知问题文档（如 `docs/RISK_REGISTER.md`、CHANGELOG Unreleased）—— 可能在册问题正是根因
- `git log` for prior fixes in the same area — **recurring bugs in the same files are an architectural smell**, not a coincidence

**External pattern search:** If the bug doesn't match a known pattern above, WebSearch for:
- "{framework} {generic error type}" — **sanitize first:** strip hostnames, IPs, file paths, SQL, customer data. Search the error category, not the raw message.
- "{library} {component} known issues"

If WebSearch is unavailable, skip this search and proceed with hypothesis testing. If a documented solution or known dependency bug surfaces, present it as a candidate hypothesis in Phase 3.

---

## Phase 3: Hypothesis Testing

Before writing ANY fix, verify your hypothesis.

1. **Confirm the hypothesis:** Add a temporary log statement, assertion, or debug output at the suspected root cause. Run the reproduction. Does the evidence match?

2. **If the hypothesis is wrong:** Before forming the next hypothesis, consider searching for the error. **Sanitize first** — strip hostnames, IPs, file paths, SQL fragments, customer identifiers, and any internal/proprietary data from the error message. Search only the generic error type and framework context: "{component} {sanitized error type} {framework version}". If the error message is too specific to sanitize safely, skip the search. If WebSearch is unavailable, skip and proceed. Then return to Phase 1. Gather more evidence. Do not guess.

3. **3-strike rule:** If 3 hypotheses fail, **STOP**. Use AskUserQuestion:
   ```
   3 hypotheses tested, none match. This may be an architectural issue
   rather than a simple bug.

   A) Continue investigating — I have a new hypothesis: [describe]
   B) Escalate for human review — this needs someone who knows the system
   C) Add logging and wait — instrument the area and catch it next time
   ```

**Red flags** — if you see any of these, slow down:
- "Quick fix for now" — there is no "for now." Fix it right or escalate.
- Proposing a fix before tracing data flow — you're guessing.
- Each fix reveals a new problem elsewhere — wrong layer, not wrong code.

---

## Phase 4: Implementation

Once root cause is confirmed:

1. **Fix the root cause, not the symptom.** The smallest change that eliminates the actual problem.

2. **Minimal diff:** Fewest files touched, fewest lines changed. Resist the urge to refactor adjacent code.

3. **Write a regression test** that:
   - **Fails** without the fix (proves the test is meaningful)
   - **Passes** with the fix (proves the fix works)

4. **Run the full test suite.** Paste the output. No regressions allowed.

5. **If the fix touches >5 files:** Use AskUserQuestion to flag the blast radius:
   ```
   This fix touches N files. That's a large blast radius for a bug fix.
   A) Proceed — the root cause genuinely spans these files
   B) Split — fix the critical path now, defer the rest
   C) Rethink — maybe there's a more targeted approach
   ```

---

## Phase 5: Verification & Report

**Fresh verification:** Reproduce the original bug scenario and confirm it's fixed. This is not optional.

Run the test suite and paste the output.

Output a structured debug report:
```
DEBUG REPORT
════════════════════════════════════════
Symptom:         [what the user observed]
Root cause:      [what was actually wrong]
Fix:             [what was changed, with file:line references]
Evidence:        [test output, reproduction attempt showing fix works]
Regression test: [file:line of the new test]
Related:         [TODOS.md items, prior bugs in same area, architectural notes]
Status:          DONE | DONE_WITH_CONCERNS | BLOCKED
════════════════════════════════════════
```

（可选）有 gstack 环境的机器可将调查沉淀为 learning 供后续会话复用（`gstack-learnings-log`）；不具备时，将结论写入仓库 `docs/` 或 CHANGELOG Unreleased 即可。

## Capture Learnings

> 触发词规则不变：仅在发现"非明显、可复用的模式/陷阱/架构洞见"时记录；显而易见的、一次性瞬态错误不记录。本插件不内置 gstack 学习库，沉淀方式按上方 Phase 5 降级说明执行。

**Types:** `pattern` (reusable approach), `pitfall` (what NOT to do), `preference`
(user stated), `architecture` (structural decision), `tool` (library/framework insight),
`operational` (project environment/CLI/workflow knowledge).

**Confidence:** 1-10. Be honest. An observed pattern you verified in the code is 8-9.
An inference you're not sure about is 4-5. A user preference they explicitly stated is 10.

**Only log genuine discoveries.** Don't log obvious things. Don't log things the user
already knows. A good test: would this insight save time in a future session? If yes, log it.

---

## Important Rules

- **3+ failed fix attempts → STOP and question the architecture.** Wrong architecture, not failed hypothesis.
- **Never apply a fix you cannot verify.** If you can't reproduce and confirm, don't ship it.
- **Never say "this should fix it."** Verify and prove it. Run the tests.
- **If fix touches >5 files → AskUserQuestion** about blast radius before proceeding.
- **Completion status:**
  - DONE — root cause found, fix applied, regression test written, all tests pass
  - DONE_WITH_CONCERNS — fixed but cannot fully verify (e.g., intermittent bug, requires staging)
  - BLOCKED — root cause unclear after investigation, escalated

> ⚠️ **配套工具声明**：本 Skill 引用的 `templates/*.md`、`scripts/*.py|.ps1|.ts`、`docs/design/*.md`、`docs/images/` 等为外部配套工具/示例，仓库未内置这些文件；引用仅作规范说明，实际使用需按需自备或从上游来源获取（不构成仓库内可访问的承诺）。