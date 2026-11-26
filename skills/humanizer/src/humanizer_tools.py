"""
Hexis Tools - Humanizer / Output Quality (L.1-L.2)

Tool handler for detecting and removing AI writing patterns from text.
Combines rule-based pattern detection with optional LLM rewriting.
"""

from __future__ import annotations

import logging
import re
from typing import Any

try:
    from .base import (
        ToolCategory,
        ToolContext,
        ToolExecutionContext,
        ToolHandler,
        ToolResult,
        ToolSpec,
    )
except ImportError:  # Also support the documented direct src import.
    from base import (
        ToolCategory,
        ToolContext,
        ToolExecutionContext,
        ToolHandler,
        ToolResult,
        ToolSpec,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AI Writing Pattern Definitions (36 patterns)
# ---------------------------------------------------------------------------

AI_PATTERNS: list[dict[str, Any]] = [
    {
        "name": "em_dash_overuse",
        "description": "Excessive em dash usage (—) where commas or periods suffice",
        "pattern": r"—",
        "threshold": 2,  # Flag if >2 per paragraph
        "suggestion": "Replace some em dashes with commas, periods, or parentheses",
    },
    {
        "name": "formulaic_opener",
        "description": "Generic opening phrases like 'In today's world' or 'It's worth noting'",
        "pattern": r"(?i)\b(in today'?s (?:world|landscape|era)|it'?s worth noting|it'?s important to|when it comes to|at the end of the day|in the realm of|in the world of)\b",
        "threshold": 1,
        "suggestion": "Start with a specific claim or observation instead",
    },
    {
        "name": "transition_crutch",
        "description": "Overuse of transitional phrases (Moreover, Furthermore, Additionally)",
        "pattern": r"(?i)^(moreover|furthermore|additionally|consequently|nevertheless|in conclusion|to summarize|all in all|in summary)[,:]?\s",
        "threshold": 1,
        "suggestion": "Let ideas flow naturally or use simpler connectors",
    },
    {
        "name": "hedge_stacking",
        "description": "Multiple hedging phrases in one sentence",
        "pattern": r"(?i)\b(it seems|perhaps|arguably|to some extent|in many ways|in a sense|one might argue|it could be said)\b",
        "threshold": 2,
        "suggestion": "Commit to your assertion or remove unnecessary hedges",
    },
    {
        "name": "adverb_inflation",
        "description": "Overuse of intensifying adverbs (incredibly, fundamentally, significantly)",
        "pattern": r"(?i)\b(incredibly|fundamentally|significantly|remarkably|profoundly|essentially|absolutely|literally|extremely)\b",
        "threshold": 2,
        "suggestion": "Show impact through specifics rather than adverbs",
    },
    {
        "name": "passive_voice",
        "description": "Excessive passive constructions",
        "pattern": r"(?i)\b(is|are|was|were|been|being)\s+(being\s+)?\w+ed\b",
        "threshold": 3,
        "suggestion": "Use active voice where possible",
    },
    {
        "name": "list_intro",
        "description": "Formulaic list introductions (Here are X things, Let's explore, Let's dive)",
        "pattern": r"(?i)(here are \d+|let'?s (?:explore|dive|look at|examine|break down|unpack)|without further ado)",
        "threshold": 1,
        "suggestion": "Jump straight into the content",
    },
    {
        "name": "metaphor_cliche",
        "description": "Overused metaphors (tip of the iceberg, game-changer, paradigm shift)",
        "pattern": r"(?i)\b(tip of the iceberg|game[ -]?changer|paradigm shift|double[ -]?edged sword|at the forefront|pave the way|shed light on|a brave new|stand at the crossroads)\b",
        "threshold": 1,
        "suggestion": "Use fresh, specific language instead",
    },
    {
        "name": "grandiose_framing",
        "description": "Unnecessarily grand framing (revolutionary, transformative, groundbreaking)",
        "pattern": r"(?i)\b(revolutionary|transformative|groundbreaking|game[ -]?changing|cutting[ -]?edge|state[ -]?of[ -]?the[ -]?art|world[ -]?class|next[ -]?generation|bleeding[ -]?edge)\b",
        "threshold": 1,
        "suggestion": "Use precise descriptors instead of superlatives",
    },
    {
        "name": "colon_listing",
        "description": "Pattern of colon followed by enumerated list items",
        "pattern": r":\s*\n\s*\d+\.\s",
        "threshold": 2,
        "suggestion": "Vary your structure; not every point needs a numbered list",
    },
    {
        "name": "rhetorical_question",
        "description": "Rhetorical questions used as transitions",
        "pattern": r"(?i)^(but what|so what|but how|what does this|how can we|what if we|have you ever|but why)\b.*\?",
        "threshold": 1,
        "suggestion": "State your point directly instead of asking then answering",
    },
    {
        "name": "triple_structure",
        "description": "Formulaic three-part structures (X, Y, and Z patterns)",
        "pattern": r"(?i)\b\w+,\s+\w+,\s+and\s+\w+\b",
        "threshold": 3,
        "suggestion": "Vary sentence structure; not everything needs three items",
    },
    {
        "name": "conclusion_signal",
        "description": "Obvious conclusion signaling phrases",
        "pattern": r"(?i)\b(in conclusion|to wrap up|to sum up|all things considered|the bottom line|the takeaway|key takeaway|final thoughts)\b",
        "threshold": 1,
        "suggestion": "End naturally without announcing the conclusion",
    },
    {
        "name": "empathy_opener",
        "description": "Performative empathy phrases",
        "pattern": r"(?i)(i understand (?:that|your|how)|i appreciate (?:that|your)|that'?s a great (?:question|point)|great question|absolutely[!,]|of course[!,])",
        "threshold": 1,
        "suggestion": "Address the substance directly",
    },
    {
        "name": "filler_phrases",
        "description": "Padding phrases that add no meaning",
        "pattern": r"(?i)\b(it goes without saying|needless to say|as we all know|as everyone knows|the fact of the matter|at this point in time|for all intents and purposes)\b",
        "threshold": 1,
        "suggestion": "Remove — these phrases carry no information",
    },
    {
        "name": "bookend_structure",
        "description": "Mirroring intro and conclusion too closely",
        "pattern": r"(?i)(as (?:we'?ve|I'?ve) (?:seen|discussed|explored|examined))",
        "threshold": 1,
        "suggestion": "End with new insight rather than restating the introduction",
    },
    {
        "name": "exclamation_enthusiasm",
        "description": "Excessive exclamation marks suggesting forced enthusiasm",
        "pattern": r"!",
        "threshold": 3,
        "suggestion": "Let content convey enthusiasm rather than punctuation",
    },
    {
        "name": "delve",
        "description": "The word 'delve' (strongly associated with AI writing)",
        "pattern": r"(?i)\bdelve\b",
        "threshold": 1,
        "suggestion": "Use 'explore', 'examine', 'look at', or 'investigate' instead",
    },
    {
        "name": "landscape_tapestry",
        "description": "Abstract nouns used as filler (landscape, tapestry, realm, arena)",
        "pattern": r"(?i)\b(the (?:landscape|tapestry|fabric|realm|arena|ecosystem|sphere) of)\b",
        "threshold": 1,
        "suggestion": "Be specific about what you're referring to",
    },
    {
        "name": "both_and",
        "description": "Overuse of 'both X and Y' parallel construction",
        "pattern": r"(?i)\bboth\s+\w+\s+and\s+\w+\b",
        "threshold": 2,
        "suggestion": "Vary sentence structure",
    },
    {
        "name": "certainly_surely",
        "description": "Filler certainty words that weaken rather than strengthen",
        "pattern": r"(?i)\b(certainly|surely|undoubtedly|undeniably|unquestionably)\b",
        "threshold": 2,
        "suggestion": "State facts directly without asserting certainty",
    },
    {
        "name": "navigate_complexity",
        "description": "'Navigate' used metaphorically (navigate the complexities)",
        "pattern": r"(?i)\bnavigate\s+(the\s+)?(complex|intricac|challeng|landscape|world)",
        "threshold": 1,
        "suggestion": "Use 'handle', 'manage', or 'deal with' instead",
    },
    {
        "name": "leverage_utilize",
        "description": "Corporate-speak verbs (leverage, utilize, optimize, synergize)",
        "pattern": r"(?i)\b(leverage|utilize|synergize|incentivize|operationalize|actualize)\b",
        "threshold": 1,
        "suggestion": "Use 'use', 'make the most of', or a specific verb",
    },
    {
        "name": "not_just_but_also",
        "description": "The 'not just X but also Y' construction",
        "pattern": r"(?i)\bnot (?:just|only|merely)\b.*\bbut (?:also|additionally)\b",
        "threshold": 2,
        "suggestion": "Simplify: state both points without the construction",
    },
    {
        "name": "email_opener",
        "description": "Email套话开场",
        "pattern": r"(?i)\b(i hope this (?:email |message )?finds you well|i am writing to|at your earliest convenience|please let me know if you have any questions|thank you for your time|looking forward to (?:hearing|your response))\b",
        "threshold": 1,
        "suggestion": "直接说明邮件目的或开门见山"
    },
    {
        "name": "academic_intro_template",
        "description": "学术论文模板化开场",
        "pattern": r"(?i)\b(in recent years|in the past few years|this paper aims to|this study aims to|we believe that|it is widely known|it is well known)\b",
        "threshold": 1,
        "suggestion": "用具体研究背景/数据代替模板句"
    },
    {
        "name": "academic_skeleton",
        "description": "学术段落骨架句（First/Next/Finally等）",
        "pattern": r"(?i)^(first,?ly|second,?ly|third,?ly|fourth,?ly|finally,?|in the first place|to begin with|in conclusion|to summarize|to sum up|all in all)\b",
        "threshold": 1,
        "suggestion": "用自然段落流代替枚举式骨架"
    },
    {
        "name": "academic_hedge_pileup",
        "description": "学术段落连续多个模糊限制",
        "pattern": r"(?i)\b(could possibly|may potentially|might possibly|can perhaps|tends to somewhat|seems to be|appears to be)\b",
        "threshold": 2,
        "suggestion": "删除冗余模糊词，保留一个即可"
    },
    {
        "name": "value_judge_superlative",
        "description": "学术/商业过度评价",
        "pattern": r"(?i)\b(comprehensive overview|valuable resource|crucial role|pivotal role|key takeaway|valuable insights|robust solution|powerful tool|invaluable insights)\b",
        "threshold": 1,
        "suggestion": "用具体数据/事实代替价值判断"
    },
    {
        "name": "leverage_utilize_repeat",
        "description": "动词冗余(leverage/utilize/optimize替代use)",
        "pattern": r"(?i)\b(leverage(?:s|d)?|utilize(?:s|d)?|optimize(?:s|d)?|synergize(?:s|d)?|incentivize(?:s|d)?|operationalize(?:s|d)?)\b",
        "threshold": 1,
        "suggestion": "用 use / make the most of / apply 替代"
    },
    {
        "name": "delve_deeper",
        "description": "delve 和 deeper 组合（强AI信号）",
        "pattern": r"(?i)\b(delve(?:s)? deeper|delve(?:s)? into|deep dive|deep-dive|deeply explore)\b",
        "threshold": 1,
        "suggestion": "用 investigate / examine / study 替代"
    },
    {
        "name": "emphasize_underscore",
        "description": "过度强调/突出",
        "pattern": r"(?i)\b(crucial(?:ly)?|essential(?:ly)?|paramount|extremely important|of utmost importance|of paramount importance|stands out|noteworthy|remarkable)\b",
        "threshold": 2,
        "suggestion": "用具体表现/数据代替空泛强调"
    },
    {
        "name": "structural_throat_clearing",
        "description": "段落开头清嗓句(There is/There are/It is)",
        "pattern": r"(?i)^(there is no denying|there is no doubt|there is a need|it is no exaggeration|it is undeniable|it is true that)\b",
        "threshold": 1,
        "suggestion": "直接陈述事实"
    },
    {
        "name": "em_dense_sentence",
        "description": "连续多个em dash堆叠",
        "pattern": r"—.*—",
        "threshold": 1,
        "suggestion": "用句号或逗号断开长句"
    },
    {
        "name": "list_intro_vague",
        "description": "含糊的列表引导",
        "pattern": r"(?i)\b(the following (?:points|aspects|factors|reasons|advantages|disadvantages)|include(?:s)? the following|are (?:shown|listed) as follows|as shown below|see below)\b",
        "threshold": 1,
        "suggestion": "用具体内容代替'如下'式引导"
    },
    {
        "name": "compelling_remarkable_overuse",
        "description": "compelling/remarkable 重复使用",
        "pattern": r"(?i)\b(compelling|remarkable|noteworthy|extraordinary|exceptional|unparalleled|unprecedented)\b",
        "threshold": 2,
        "suggestion": "保留一个最有依据的，删除其他"
    }
]

# Compile once: detection runs before and after every rewrite pass.
_COMPILED_PATTERNS = tuple(
    (pattern_def, re.compile(pattern_def["pattern"], re.MULTILINE))
    for pattern_def in AI_PATTERNS
)
_SPECIFIC_PATTERN_NAMES = frozenset({"leverage_utilize_repeat", "delve_deeper"})
_SPECIFIC_COMPILED = tuple(
    (pattern_def["name"], compiled)
    for pattern_def, compiled in _COMPILED_PATTERNS
    if pattern_def["name"] in _SPECIFIC_PATTERN_NAMES
)


def detect_ai_patterns(text: str) -> list[dict[str, Any]]:
    """
    Detect AI writing patterns in text.

    Returns list of detected patterns with match counts and locations.
    """
    detections: list[dict[str, Any]] = []

    specific_matches = [match for _, compiled in _SPECIFIC_COMPILED for match in compiled.finditer(text)]
    for pattern_def, compiled in _COMPILED_PATTERNS:
        threshold = pattern_def["threshold"]
        matches = list(compiled.finditer(text))

        # Specific patterns take precedence over broad counterparts; don't
        # count an overlapping match twice in the aggregate score.
        if pattern_def["name"] not in _SPECIFIC_PATTERN_NAMES:
            matches = [m for m in matches if not any(
                m.start() < specific_match.end() and specific_match.start() < m.end()
                for specific_match in specific_matches
            )]

        if len(matches) >= threshold:
            spans = []
            for m in matches[:5]:  # Limit to first 5 examples
                start = max(0, m.start() - 20)
                end = min(len(text), m.end() + 20)
                spans.append(text[start:end].strip())

            detections.append({
                "pattern": pattern_def["name"],
                "description": pattern_def["description"],
                "count": len(matches),
                "threshold": threshold,
                "suggestion": pattern_def["suggestion"],
                "examples": spans,
            })

    return detections


def _effective_word_count(text: str) -> int:
    """Count English words plus CJK ideographs.

    CJK text has no word separators, so ``str.split()`` alone would count an
    entire Chinese paragraph as one word and short-circuit scoring to 0.0.
    """
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    words = sum(1 for word in text.split() if any(ch.isalnum() for ch in word))
    return cjk + words


def compute_ai_score(text: str, detections: list[dict[str, Any]]) -> float:
    """
    Compute an AI-ness score from 0.0 (human) to 1.0 (very AI-like).

    Based on pattern density relative to text length.
    """
    if not text.strip():
        return 0.0

    word_count = _effective_word_count(text)
    if word_count < 20:
        return 0.0

    total_hits = sum(d["count"] for d in detections)
    unique_patterns = len(detections)

    # Normalize: hits per 100 words, weighted by pattern diversity
    density = (total_hits / word_count) * 100
    diversity_factor = min(unique_patterns / 10, 1.0)

    score = min((density * 0.3 + diversity_factor * 0.7), 1.0)
    return round(score, 2)


# ---------------------------------------------------------------------------
# L.1 & L.2: Humanize Text Tool
# ---------------------------------------------------------------------------


class HumanizeTextHandler(ToolHandler):
    """Detect and optionally rewrite AI writing patterns in text."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="humanize_text",
            description=(
                "Analyze text for AI writing patterns (em dashes, formulaic transitions, "
                "'delve', etc.) and optionally rewrite to sound more natural. "
                "Returns pattern detections, AI-ness score, and rewritten text if requested."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to analyze and optionally humanize.",
                    },
                    "rewrite": {
                        "type": "boolean",
                        "description": "If true, produce a rewritten version with AI patterns removed. Uses an LLM pass.",
                    },
                },
                "required": ["text"],
            },
            category=ToolCategory.EXTERNAL,
            energy_cost=1,
            is_read_only=True,
            supports_parallel=True,
            optional=True,
        )

    async def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        text = arguments.get("text", "")
        do_rewrite = arguments.get("rewrite", False)

        if not text.strip():
            return ToolResult.error_result("No text provided")

        # Detect patterns
        detections = detect_ai_patterns(text)
        score = compute_ai_score(text, detections)

        result: dict[str, Any] = {
            "ai_score": score,
            "pattern_count": len(detections),
            "total_hits": sum(d["count"] for d in detections),
            "detections": detections,
        }

        # Optional LLM rewrite
        if do_rewrite and detections:
            pool = context.registry.pool if context.registry else None
            if pool:
                try:
                    rewritten = await self._rewrite_text(text, detections, pool)
                    if rewritten:
                        result["rewritten"] = rewritten
                        # Re-score the rewritten version
                        new_detections = detect_ai_patterns(rewritten)
                        result["rewritten_ai_score"] = compute_ai_score(rewritten, new_detections)
                except Exception as e:
                    result["rewrite_error"] = str(e)

        return ToolResult.success_result(result)

    async def _rewrite_text(
        self, text: str, detections: list[dict[str, Any]], pool: Any
    ) -> str | None:
        """Use an LLM to rewrite text removing detected AI patterns."""
        from core.llm import chat_completion
        from core.llm_config import load_llm_config

        pattern_list = "\n".join(
            f"- {d['pattern']}: {d['suggestion']}" for d in detections[:10]
        )

        prompt = (
            "Rewrite the following text to sound more natural and human. "
            "Remove the detected AI writing patterns listed below. "
            "Preserve the original meaning and tone. Do NOT add new content. "
            "Return ONLY the rewritten text, nothing else.\n\n"
            f"Detected AI patterns to fix:\n{pattern_list}\n\n"
            f"Original text:\n{text}"
        )

        try:
            llm_config = await load_llm_config(pool, preference="cheap")
        except Exception:
            llm_config = await load_llm_config(pool)

        response = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            **llm_config,
        )

        if response and response.get("content"):
            content = response["content"]
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block["text"]
            elif isinstance(content, str):
                return content

        return None


# ---------------------------------------------------------------------------
# L.1: Output Post-Processor Hook
# ---------------------------------------------------------------------------


def post_process_skip_reason(detections: list[dict[str, Any]], score: float) -> str:
    """Explain why the output post-processor did not rewrite a text."""
    if not detections:
        return "no patterns found"
    return f"score too low ({score:.2f})"


class PostProcessOutputHandler(ToolHandler):
    """Apply output post-processing pipeline to text before delivery."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="post_process_output",
            description=(
                "Apply configured output post-processing transformations to text. "
                "Runs the humanizer and any other configured processors. "
                "Use this before delivering important content to channels."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to post-process.",
                    },
                    "processors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Processors to apply. Options: 'humanizer'. Defaults to all enabled processors.",
                    },
                },
                "required": ["text"],
            },
            category=ToolCategory.EXTERNAL,
            energy_cost=2,
            is_read_only=True,
            supports_parallel=True,
            optional=True,
        )

    async def execute(
        self, arguments: dict[str, Any], context: ToolExecutionContext
    ) -> ToolResult:
        text = arguments.get("text", "")
        processors = arguments.get("processors", ["humanizer"])

        if not text.strip():
            return ToolResult.error_result("No text provided")

        result_text = text
        applied = []

        for proc in processors:
            if proc == "humanizer":
                detections = detect_ai_patterns(result_text)
                score = compute_ai_score(result_text, detections)

                if detections and score > 0.3:
                    # Only rewrite if score is meaningfully high
                    pool = context.registry.pool if context.registry else None
                    if pool:
                        try:
                            handler = HumanizeTextHandler()
                            rewritten = await handler._rewrite_text(result_text, detections, pool)
                            if rewritten:
                                result_text = rewritten
                                applied.append({
                                    "processor": "humanizer",
                                    "original_score": score,
                                    "patterns_found": len(detections),
                                })
                        except Exception as e:
                            applied.append({
                                "processor": "humanizer",
                                "error": str(e),
                            })
                else:
                    applied.append({
                        "processor": "humanizer",
                        "skipped": True,
                        "reason": post_process_skip_reason(detections, score),
                        "score": score,
                    })

        return ToolResult.success_result({
            "text": result_text,
            "processors_applied": applied,
        })


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_humanizer_tools() -> list[ToolHandler]:
    """Create humanizer and output post-processing tool handlers."""
    return [
        HumanizeTextHandler(),
        PostProcessOutputHandler(),
    ]
