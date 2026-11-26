"""Conservative Chinese academic de-templating backend.

This backend diagnoses Chinese academic style risks and produces constraints for
an Agent LM. It does not perform unconstrained synonym replacement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from providers.agent_lm_quality import build_rewrite_request, evaluate_rewrite
except ImportError:  # package import (src.backends.chinese): sibling package
    from ..providers.agent_lm_quality import build_rewrite_request, evaluate_rewrite


@dataclass(frozen=True)
class ChineseFinding:
    category: str
    severity: str
    phrase: str
    reason: str
    action: str


class ChineseAcademicHumanizer:
    language = "zh"
    domain = "academic"
    PATTERNS = (
        ("C1", "MEDIUM", r"本文(首先|将|主要)", "流程宣告可能没有提供研究信息", "改为具体研究对象或删除"),
        ("C2", "MEDIUM", r"进行(深入)?(研究|分析|探讨)", "空泛动词未说明实际动作", "补充对象、方法或结果"),
        ("C3", "MEDIUM", r"(首先|其次|最后|综上所述)[，,]", "连续连接词可能形成模板化结构", "仅保留承担逻辑关系的连接词"),
        ("C4", "HIGH", r"(具有|有着)重要(的)?(意义|价值)", "价值判断缺少可核验对象", "改为具体贡献或删除"),
        ("C5", "HIGH", r"(充分|有效地)?证明了", "结论强度可能超过实验或模型证据", "核对证据后改为支持、表明或保留"),
        ("C6", "MEDIUM", r"从而(为|实现|达到)", "结果与目标之间可能缺少中间证据", "补充机制、条件或指标"),
        ("C7", "OPTIONAL", r"可以看出|不难发现|显然", "可能是无信息量的观察式开场", "直接陈述图表或结果"),
    )

    def diagnose(self, text: str) -> list[dict]:
        findings: list[dict] = []
        for category, severity, pattern, reason, action in self.PATTERNS:
            for match in re.finditer(pattern, text):
                findings.append({
                    "category": category,
                    "severity": severity,
                    "phrase": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "reason": reason,
                    "action": action,
                    "language": self.language,
                })
        return findings

    def build_rewrite_request(self, text: str, findings: list[dict]) -> dict:
        request = build_rewrite_request(text, findings)
        request.update({
            "language": self.language,
            "domain": self.domain,
            "instruction": (
                "以中文学术语体保守改写。只处理 findings 标记的问题；保留作者原意、"
                "限定条件、术语、变量、公式、数字、单位、引用、图表编号和模型结论。"
                "不要用固定同义词替换制造新的模板。"
            ),
            "constraints": request["constraints"] + [
                "不要把假设改成事实，不要把支持改成证明，不要删除适用范围。",
                "数学建模文本中保留变量、目标函数、约束和算法名称。",
            ],
        })
        return request

    def evaluate(self, original: str, rewritten: str) -> dict:
        result = evaluate_rewrite(original, rewritten)
        result.update({"language": self.language, "domain": self.domain})
        return result

    def rewrite_suggestions(self, text: str) -> list[dict]:
        """Return reviewable suggestions, never silently mutate the document."""
        return [finding for finding in self.diagnose(text)
                if finding["severity"] in {"HIGH", "MEDIUM"}]
