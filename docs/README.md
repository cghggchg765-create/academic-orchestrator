# 文档导航

数学建模多智能体协同系统的文档与规范索引。机器可读协议见 `spec/`，契约检查见 `scripts/lint_contracts.py`。

## 入口

| 文档 | 内容 |
|---|---|
| [README](../README.md) | 系统总览、架构图、覆盖环节、使用方式、测试与契约检查 |
| [迭代工作流说明](迭代工作流说明.md) | 状态统一节点、标准项目结构、单独调用节点、迭代循环、插件适配 |
| [冒烟验证报告](冒烟验证报告.md) | 链路实测产物与验证口径（历史记录，最新以契约检查为准） |

## 机器可读协议（spec/）

| 文件 | 内容 |
|---|---|
| [result.schema.json](../spec/result.schema.json) | Agent 结果 envelope：必填字段、状态/审阅裁决枚举、产物与哈希 |
| [review_protocol.json](../spec/review_protocol.json) | 独立评审、问题修复与复跑协议（≤2 次修复、BLOCKED 不降级） |
| [sync_compatibility.json](../spec/sync_compatibility.json) | 已有材料同步兼容流程与质量门禁（code/data/paper gate） |

## 核心 Skill

- [mm-iteration-engine](../skills/mm-iteration-engine/SKILL.md)：状态底座 + 迭代引擎 + 审阅配对 + 检索地址注册表
- [mathematical-modeling](../skills/mathematical-modeling/SKILL.md)：9 阶段主控流程与门控
- [sync-and-compatibility](../skills/sync-and-compatibility/SKILL.md)：已有论文/代码/数据接入与转换协议

## 目录说明

- `docs/smoke/`、`docs/smoke_iteration/` 为历史冒烟实测产物（含旧命名示例，不作为现行规范示范；现行规范以 mm-iteration-engine SKILL 为准）。
- `ref/` 为本地参考项目（不入库），文档中的引用为外部依赖说明。
