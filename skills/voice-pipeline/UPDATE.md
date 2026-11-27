# 更新与维护手册

拓扑只有两层：

```
C:\Users\11352\.zcode\skill-sources\voice-pipeline   ← 实际内容
                    ↑ Junction
C:\Users\11352\.zcode\skills\voice-pipeline          ← zcode 正式入口
                    ↑ Junction
豆包 .user_skills\voice-pipeline                      ← 只引用 zcode 入口
```

`voice-pipeline` 自身不是 git 仓库；修改 `SKILL.md`、`registry.json`、`scripts` 直接生效。

## 一、工具一览

| 工具 | 用途 |
|---|---|
| `scripts/doctor.py` | 检查能力地图 schema、入口、关键文件、Junction、前端名称 |
| `scripts/update.py` | 对 registry 中 git-backed 子技能执行 `git pull`，再自检；非 git 技能明确提示手动更新 |
| `assets/manifest.template.json` | 协同台账模板：谁、什么角色、吃了什么、吐了什么、QA 过没过、下一棒 |

## 二、常规更新

```powershell
python "C:\Users\11352\.zcode\skills\voice-pipeline\scripts\update.py"
```

它会：
1. 从 `registry.json` 找到每个技能对应的 git 仓库（同一仓库多个技能只拉一次）；
2. 对 git 仓库执行 `git -c http.proxy= -c https.proxy= pull --ff-only`；
3. 非 git 技能打印 `SKIP`，提示手动更新；
4. 打印更新前后 commit 与变更文件；
5. 若 `SKILL.md` 有变更，提示“总控下次会读新流程；能力边界/入口/依赖变化时复核 registry”；
6. 自动跑 `doctor.py` 自检。

只检查、不拉取：

```powershell
python "C:\Users\11352\.zcode\skills\voice-pipeline\scripts\doctor.py"
python "...\voice-pipeline\scripts\doctor.py" --json
```

## 三、更新后会发生什么

- zcode 入口与豆包 Junction 指向同一份内容，更新后**两侧立即生效**，不需要重建链接。
- 总控不保存子技能流程，只存能力地图、角色、交接与依赖。子技能改写自己的 `SKILL.md` 后，总控下次调用会读到新内容，**无需同步修改**。
- 只有“新增技能目录”“目录改名”“能力边界变化”才需要改 `registry.json` 与 Junction。
- 子技能只存在一份；豆包侧只放指向 zcode 入口的 Junction。`doubao-human-signal` 是豆包内置技能，直接读内置入口，不复制。

## 四、需要人工处理的情况

| 情况 | 表现 | 处理 |
|---|---|---|
| 新增降防御/去 AI 味技能 | `doctor.py` 报 FAIL 或能力缺口 | 在 `registry.json` 加能力卡；在 zcode `skills` 建入口；豆包建指向该入口的 Junction；重跑 doctor |
| 技能目录改名/移动 | FAIL 路径不存在或 Junction 指向不一致 | 改 `registry.json` 的 `path` 与 `entry`，同步重建两侧入口 |
| 能力边界变化 | 路由开始频繁不匹配 | 改该技能的 `best_at` / `not_for` / `inputs` / `outputs`；不改流程细节 |
| 子技能新增 reference | `doctor.py` 报 `requires_files` 缺失 | 把新 reference 加进 `requires_files`，或确认它是否真是必需 |
| 子技能从 git 变为非 git | `update.py` 打印 `SKIP` | 手动更新；不要用复制覆盖破坏 Junction 模型 |
| 豆包内置技能升级 | `doubao-human-signal` 路径不变 | 直接读内置入口；不要复制到 zcode |

新增技能能力卡的最小字段：

`slot / stage / name / path / entry / repo / stars / maturity / role / roots / best_at / inputs / outputs / not_for / done_when / requires_files / depends / fallback`

`role` 只能是：`narrative`（叙事重构）、`diagnose`（诊断/评分）、`edit`（最小编辑）、`rewrite`（改写）。

`roots` 只能是：`zcode`、`doubao`、`builtin`。

## 五、协同台账

复制 `assets/manifest.template.json`，只记协同事实：

```json
{
  "request": "用户原话摘要",
  "slug": "text1",
  "context": {"language": "zh", "genre": "paper-abstract", "mode": "rewrite", "strength": "medium"},
  "assignments": [
    {"stage": "V0", "skill": "anti-defensive-writing", "role": "narrative", "status": "done",
     "inputs": ["..."], "outputs": ["..."],
     "qa": {"owner": "anti-defensive-writing", "status": "pass", "notes": ""}, "next": "V2"}
  ],
  "handoffs": [{"from": "anti-defensive-writing", "to": "humanizer-zh", "artifact": "draft.md"}],
  "open_questions": [],
  "next": ""
}
```

台账只回答：谁、什么角色、吃了什么、吐了什么、它的 QA 过没过、下一棒给谁。总控不替子技能跑 QA，也不替它改稿。

## 六、回滚

`voice-pipeline` 自身没有 git 历史。大改前先复制一份 `SKILL.md` / `registry.json` / `scripts` 到同目录的临时备份，确认后再删备份；不要把备份留在技能入口里。

子技能若有 git 仓库，回滚在对应仓库执行：

```powershell
git -C <repo> log -1 --format=%h
git -C <repo> reset --hard <old-commit>
```

## 七、禁止事项

- 不要把子技能复制进豆包 `.user_skills`——豆包侧只放指向 zcode 入口的 Junction。
- 不要在总控里抄子技能的步骤、禁用词表、评分标准、平台模板；这些以子技能 `SKILL.md` 为准。
- 不要在总控里替子技能改写、评分、修 QA；总控只做匹配、交接、重路由。
- 不要在 `doctor.py` 未通过时继续调度。
- 不要手工改 `registry.json` 的 `path` 指向仓库内部；对外路径统一是 zcode 入口。
- 不要承诺 AI 检测通过、降重、查重；这不是本管线目标。
