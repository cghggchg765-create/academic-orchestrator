---
name: mm-audit
description: 接手审计已有数学建模项目（读题→比对→验证→标准化修复）
---

对已有项目（无论是否由本系统初始化）执行接手审计与修复闭环，参数为项目目录 $ARGUMENTS：

```bash
python state/state_utils.py project-audit --dir <项目目录> [--source <题目原文>]
python state/state_utils.py project-repair --dir <项目目录> [--apply]   # 先预览，确认后 --apply
```

审计项：题目事实锁定（SHA-256 漂移）、标准结构（目录+占位文件）、9 份节点首页、registry 与 NODES 一致性、状态-产物一致性（completed 但产物缺失→级联失效；有产物未登记→提示补登记）、旧命名残留。

规则：

1. `project-repair --apply` 只补建缺失的标准设施，**绝不覆盖已有文件与状态**；
2. 题目锁定缺失/漂移时不代填：先阅读题目 → `problem_guard.py create` 重新锁定；含图形题目先 `figures --mode vision|human` 处理；
3. 修复后再次 `project-audit`，向用户收敛剩余问题清单与下一步建议（如"补跑 N1 选题拆解"）。
