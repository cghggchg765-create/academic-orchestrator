# 更新与维护手册

拓扑只有两层：

```
C:\Users\11352\.zcode\skills\<技能名>      ← zcode 正式入口（实际内容）
                    ↑ Junction
豆包 .user_skills\<技能名>                 ← 只引用 zcode 入口
```

总控 `figure-pipeline` 也在 `.zcode\skills\figure-pipeline`。豆包侧不直接指向任何仓库目录。

## 一、工具一览

| 工具 | 用途 |
|---|---|
| `scripts/doctor.py` | 检查能力地图 schema、入口、关键文件、Junction、依赖与环境 |
| `scripts/doctor.py --deep` | 额外探测 Graphviz、drawio CLI、image2ppt doctor、Nature 后端 |
| `scripts/update.py` | 一键 `git pull` 所有子技能仓库，打印 commit 与变更文件，再自检 |
| `assets/manifest.template.json` | 协同台账模板：谁、什么角色、吃了什么、吐了什么、QA 过没过、下一棒 |
| `figure-system.json` | 可选共享上下文；由 S2 生成/维护，总控只传路径，不自己定义字号/色板 |

## 二、常规更新

```powershell
python "C:\Users\11352\.zcode\skills\figure-pipeline\scripts\update.py"
```

它会：
1. 从 `registry.json` 找到每个技能对应的 git 仓库（同一仓库的多个技能只拉一次）；
2. 执行 `git -c http.proxy= -c https.proxy= pull --ff-only`（本机全局 git 配了不存在的代理，必须清空）；
3. 打印更新前后 commit 与变更文件；
4. 若 `SKILL.md` 有变更，提示“总控下次会读新流程；能力边界/入口/依赖变化时复核 registry”；
5. 自动跑 `doctor.py` 自检。

更新后深度检查：

```powershell
python "...\figure-pipeline\scripts\update.py" --deep
```

只检查、不拉取：

```powershell
python "...\figure-pipeline\scripts\doctor.py"
python "...\figure-pipeline\scripts\doctor.py" --deep
```

## 三、更新后会发生什么

- zcode 入口与豆包 Junction 都指向同一份内容，`git pull` 后**两侧立即生效**，不需要重建链接。
- 总控不保存子技能流程，只存能力地图、角色、交接与依赖。子技能改写自己的 `SKILL.md` 后，总控下次调用会读到新内容，**无需同步修改**。
- 只有“新增技能目录”“目录改名”“能力边界变化”才需要改 `registry.json` 与 Junction。
- 总控自身不在 git 仓库里；修改 `SKILL.md`/`registry.json`/`scripts` 直接生效。

## 四、需要人工处理的情况

| 情况 | 表现 | 处理 |
|---|---|---|
| 仓库新增绘图技能 | `doctor.py` 报 WARN `unregistered` | 在 `registry.json` 加能力卡；在 zcode `skills` 建入口；豆包建指向该入口的 Junction；重跑 doctor |
| 技能目录改名/移动 | FAIL 路径不存在或 Junction 指向不一致 | 改 `registry.json` 的 `path` 与 `entry`，同步重建两侧入口 |
| 能力边界变化（新增/失去某类能力） | 路由开始频繁不匹配 | 改该技能的 `best_at` / `not_for` / `inputs` / `outputs`；不改流程细节 |
| 新增 Python 依赖 | 脚本报 `ModuleNotFoundError` | `python -m pip install <包>`；补 `DEP_MAP` 与 `depends` |
| 相对支撑路径被改 | `nature-figure` 找不到 `../nature-shared` | 确认 `nature-shared` 入口仍在 zcode 与豆包两侧 |
| 上游改了入口脚本/命令 | `doctor.py` 报 `requires_files` 缺失 | 更新 `requires_files`；Read 新 `SKILL.md` 后再调路由 |

新增技能能力卡的最小字段：

`slot / stage / name / path / entry / repo / stars / role / best_at / inputs / outputs / not_for / done_when / requires_files / depends / fallback`

`role` 只能是：`decide`（决策）、`produce`（生产）、`audit`（审计/规范）、`convert`（格式转换）、`structure`（结构图）、`rebuild`（重建）。

## 五、协同台账

复制 `assets/manifest.template.json`，只记协同事实：

```json
{
  "request": "用户原话摘要",
  "slug": "fig1",
  "context": {"journal": "Nature", "format": "pdf", "figure_system": ""},
  "assignments": [
    {"figure": "fig1", "skill": "nature-figure", "role": "auditor", "status": "done",
     "inputs": ["..."], "outputs": ["..."],
     "qa": {"owner": "nature-figure", "status": "pass", "notes": ""}, "next": ""}
  ],
  "handoffs": [{"from": "scientific-figure-making", "to": "nature-figure", "artifact": "fig.pdf"}],
  "open_questions": [],
  "next": ""
}
```

台账只回答：谁、什么角色、吃了什么、吐了什么、它的 QA 过没过、下一棒给谁。总控不替子技能跑 QA，也不替它修图。

## 六、回滚

`git pull` 是快进合并，回滚在对应仓库执行：

```powershell
git -C <repo> log -1 --format=%h
git -C <repo> reset --hard <old-commit>
```

不要用复制备份覆盖技能目录，否则会破坏 Junction 模型。

## 七、禁止事项

- 不要把子技能复制进豆包 `.user_skills`——豆包侧只放指向 zcode 入口的 Junction。
- 不要在总控里抄子技能的步骤、参数、栏宽、DPI、字体、统计规则；这些以子技能 `SKILL.md` 为准。
- 不要在总控里替子技能画图、跑检验、修 QA；总控只做匹配、交接、重路由。
- 不要在 `doctor.py` 未通过时继续调度。
- 不要手工改 `registry.json` 的 `path` 指向仓库内部；对外路径统一是 zcode 入口。

## 八、已知 WARN 的含义

| WARN | 含义 | 是否阻塞 |
|---|---|---|
| `image2ppt:ocr` | `PADDLE_OCR_TOKEN` 未配；图像 API（gpt-image-2）已配置 | 不阻塞图像生成；OCR 走本地 builtin-ink |
| `drawio:invoke` | 子技能 frontmatter 带 `disable-model-invocation: true` | 不阻塞；不自动触发时点名或由总控加载 |
| `unregistered` | 仓库里出现绘图相关新技能 | 不阻塞当前流程；决定是否注册 |
| `graphviz`（仅当既无 PATH 也无安装） | 自动布局不可用 | 不阻塞；手工坐标或 Mermaid |
