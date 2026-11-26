# 插件内写作质量与自然化改写

本模块只使用宿主 Agent LM 完成候选改写，不要求用户本地部署大模型、不下载模型权重、不启动 GPU 推理服务。

## 外部开源方案定位

候选项目登记在仓库根目录的 `vendor_writing_quality_manifest.json`：

- LanguageTool：语法与风格检查参考，LGPL-2.1。
- Vale：可审计风格规则参考，MIT。
- proselint：英文 prose 检查参考，BSD-3-Clause。
- textstat：文本统计指标参考，MIT。
- Binoculars：仅研究性检测参考，许可证和模型条款未核验，不接入生产门禁。

这些项目当前均未作为运行时依赖下载到插件中。这样可以保持插件轻量、离线可用，并避免外部模型、服务和许可证把宿主环境变成部署任务。

## 语言路由与改写权限

确定性层按语言提供诊断和保护，但不负责真正改写。中文学术/数学建模文本由 `skills/humanizer/src/backends/chinese.py` 生成风险发现和 masked request；实际候选文本必须由插件加载的对应中文子 Agent 执行。请求声明 `executor=host_plugin_subagent` 且 `local_rewrite_permitted=false`，返回候选后再由本地 provider 验收。

中文 C1-C7 规则是上下文相关的风险提示，不是机械替换表。公式、变量、数字、单位、引用、图表编号、模型假设和结论限定条件必须保持；中文去模板化不能把“支持”改成“证明”，也不能把假设改成事实。

## 工作流

```text
检测规则
→ 保护公式/代码/数字/单位/引用键
→ Agent LM 生成候选改写
→ 恢复保护片段
→ 检查主张/引用/数值是否保持
→ 二次检测
→ reviewer 独立复核
```

`skills/humanizer/src/providers/agent_lm_quality.py` 提供统一的保护与评估契约。改写失败、保护片段丢失或主张发生变化时必须 `FAIL`，不能用“AI 分数下降”掩盖内容退化。

## 评价边界

“去 AI 化”在本项目中指减少模板化、机械化和空泛表达，提升自然、准确、可核验的学术表达；不承诺规避检测器，不用于伪造作者身份，也不以检测器分数作为学术诚信结论。

## 本地 smoke

```bash
python scripts/evals/run_writing_quality.py
```

结果写入 `evals/results/writing-quality/smoke.json`。外部 Agent LM 改写结果必须保留原文、候选文本、提示词版本、输入输出 SHA-256 和人工确认记录。

数学建模结果与图表的可追溯记录使用 `shared/contracts/math_modeling/` 下的 Problem Brief、Model Card、Experiment Manifest、Result Ledger、Verification Matrix 和 Figure Trace schema。可用以下命令检查 source data → transformation → figure/table → manuscript claim 链路：

```bash
python scripts/validate_math_model_trace.py path/to/figure-trace.json --root .
```
