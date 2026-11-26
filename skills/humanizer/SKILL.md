---
name: humanizer
description: "Detect and remove AI writing patterns to produce natural, human-sounding prose. 36 pattern types, AI-ness scoring. Works on any prose: academic papers, essays, reports, blog posts, documentation. Triggers: humanize, de-AI, remove AI voice, natural writing, AI detection, 去AI化, 去AI味, 降低AI率, 太像AI写的, 机械感, 润色使表达自然, AI痕迹, 论文降AI, 文章像机器写的. Pairs with academic-humanize for academic text."
metadata:
  category: creative
  version: "2.1.0"
---

# AI Writing Pattern Detection and Removal

## 🔴 加载资格与委托守则（必须读）

本技能是 **去 AI 化（humanize）子代理** 的专项工具，**仅供 `humanize` 子代理加载执行**。

- 若你是主对话主 agent：需要对论文/文本做 AI 痕迹检测或去 AI 化改写时，派发 `subagent_type=humanize` 子代理；**不得自己加载本技能直接改写论文正文**（改写属于 writing 职责，检测属于 humanize 职责）。
- humanize 检测报告落 `state/reports/`；发现 AI 痕迹 → 由 writing 子代理按报告修订 → 复审。

Analyze text for telltale AI-generated writing patterns and rewrite it to sound natural, varied, and human-authored.

## When to Use

- User asks to "humanize" or "make this sound more natural" or "remove the AI voice"
- Drafting outgoing communications (emails, posts, messages) that should not read as AI-generated
- Editing content that will be published under the user's name
- User flags specific text as "sounding too AI"
- Before submitting academic papers to check for AI traces

## Workflow

### 🔴 STEP 1: Analyze — Run 36-pattern detection
Run `detect_ai_patterns(text)` from `src/humanizer_tools.py`.

Coverage includes:
- **General AI**: formulaic openers, transition crutches, hedge stacking, adverb inflation, filler phrases
- **Email AI**: "I hope this message finds you well", "I am writing to", "at your earliest convenience", "please let me know if you have any questions"
- **Academic AI**: "in recent years", "this paper aims to", "comprehensive overview", "valuable resource", "First...Next...Finally" skeleton, "we believe that"
- **Structural AI**: colon listing, triple structure, rhetorical questions, bookend structure, both_and, not_just_but_also
- **Tone AI**: empathy openers, exclamation enthusiasm, sycophantic tone, grandiose framing, metaphor cliche

Output: `[{pattern, description, count, threshold, suggestion, examples}]`

### 🔴 STEP 2: Score — Compute AI-ness Score
```
score = min((density × 0.3 + diversity × 0.7), 1.0)
density = total_hits / word_count × 100
diversity = min(unique_patterns / 10, 1.0)
```

| Score | Level | Action |
|-------|-------|--------|
| 0.0~0.2 | 🟢 Natural | No action needed |
| 0.2~0.4 | 🟡 Light | Selective fixes |
| 0.4~0.6 | 🟠 Moderate | Rewrite recommended |
| 0.6~0.8 | 🔴 Strong | Full rewrite |
| 0.8~1.0 | 🔴 Severe | Major rewrite |

🔴 **CHECKPOINT**: Show score to user. Ask: "Score is X.X. Proceed with rewrite?"

### STEP 3: Determine target voice
Ask or infer desired tone (one question at a time):
- Casual conversational (texting a friend)
- Professional but warm (work email)  
- Authoritative and concise (executive brief)
- Academic but natural (research paper)

### 🔴 STEP 4: Rewrite — Apply human patterns
Transformations that mimic natural writing:

| Rule | Do This | Don't Do This |
|------|---------|---------------|
| Sentence length | Mix short(4-8) + long(20-30) | Uniform 15-word sentences |
| Openings | Start with specific claim | "It's worth noting that..." |
| Transitions | Natural flow or simple connectors | "Moreover, Furthermore, Additionally" |
| Voice | Active >70% | Excessive passive |
| Specificity | "The 3pm demo" | "The upcoming presentation" |
| Imperfection | Occasional "And" / "But" start | Perfectly structured every sentence |

### STEP 5: Review — Quality check
- ✅ Preserved original meaning? (never change facts)
- ✅ AI-ness Score re-computed? (should drop ≥40%)
- ✅ Register matched? (legal ≠ blog post)
- ✅ No false claims added?

🔴 **CHECKPOINT**: Show before/after diff to user. Ask for confirmation.

## Failure Mode Recovery

| Scenario | First Fix | Fallback |
|----------|-----------|----------|
| `detect_ai_patterns` fails | Retry once | Return empty detections, score=0.0 |
| Tool `humanize_text` unavailable | Manual rewrite using Step 4 table | Skip rewrite, return detection only |
| Score suspicious (all 0 or all 1) | Check text length <20 words? If yes, skip | Log warning, assume 0.5 |
| LLM rewrite pass fails | Fall back to rule-based patterns only | Return rule-based result |
| User rejects rewrite | Keep original text | Mark as "user rejected" |

## Anti-Patterns (Do NOT Do)

| # | Forbidden | Why | Instead |
|---|-----------|-----|---------|
| 1 | Change factual claims | Voice ≠ content | Keep all facts identical |
| 2 | Dumb down sophisticated content | Complex ideas are fine | Keep vocabulary, fix structure |
| 3 | Over-correct natural text | Clear structure is good writing | Only fix detected patterns |
| 4 | Add user's personal details | Hallucination risk | Only use provided content |
| 5 | Force casual tone in academic | Register mismatch | Respect document type |
| 6 | Remove all passive voice | Academic writing needs some | Only reduce excessive passive |

## Python Implementation

Located at `src/humanizer_tools.py`:
- `detect_ai_patterns(text)` → 36 pattern detection
- `compute_ai_score(text, detections)` → 0.0~1.0 scoring
- `create_humanizer_tools()` → Tool factory

```python
from src.humanizer_tools import detect_ai_patterns, compute_ai_score

text = "In this paper, we delve into the intricate landscape of..."
detections = detect_ai_patterns(text)
score = compute_ai_score(text, detections)
print(f"AI-ness Score: {score}")
```
