"""
LOCOMO Benchmark Prompts
========================

Answer generation and category-specific judge prompts for the LOCOMO
benchmark (Snap Research, ACL 2024). Uses the industry-standard J-score
methodology: binary LLM judge (CORRECT/WRONG) on categories 1-4.

Category mapping:
    1 = multi-hop (282 questions)
    2 = temporal reasoning (321 questions)
    3 = open-domain (96 questions)
    4 = single-hop (841 questions)
    5 = adversarial (446 questions) -- excluded from scoring
"""

from __future__ import annotations

from datetime import datetime as _datetime
from typing import Any


# ===============================================================================
# CATEGORY NAMES
# ===============================================================================

CATEGORY_NAMES: dict[int, str] = {
    1: "multi-hop",
    2: "temporal",
    3: "open-domain",
    4: "single-hop",
    5: "adversarial",
}

CATEGORIES_TO_EVALUATE: list[int] = [1, 2, 3, 4]


# ===============================================================================
# ANSWER GENERATION PROMPT
# ===============================================================================

ANSWER_GENERATION_PROMPT = """You are answering a question using retrieved memories from past conversations. Follow these reasoning steps IN ORDER.

## Step 1: SCAN ALL MEMORIES
Read EVERY memory below from first to last. For each one that contains information relevant to the question, note it. Do NOT stop after finding the first relevant memory — important details are often scattered across many memories, including ones far down the list. Give equal weight to ALL memories regardless of position — a memory near the end is just as likely to contain the answer as one near the beginning. In these memories, "User" refers to the main person whose memories these are.

## Step 2: ENTITY VERIFICATION
Confirm each relevant memory is about the correct person/entity. If the question asks "What does Person A like?" and a memory says "Person B likes X", do NOT use that memory to answer about Person A. In two-person conversations, both speakers' actions are relevant — if the question asks about person A and a memory attributes an action to person B (the other speaker), that information is still valid evidence from their shared conversations, but always check the attribution is correct.

## Step 3: COMBINE AND CROSS-REFERENCE
- COMBINE facts from multiple memories about the same topic. If one memory says "won first place" and another says "performed a piece titled X," those describe the same event — connect them.
- For listing/counting questions, extract EVERY distinct item from ALL memories. A single memory may contain multiple items. Think about what CATEGORIES of answers the question could have, then re-scan specifically for each category.
- For counting questions ("how many times", "how many X"), enumerate each distinct instance explicitly with its date or context BEFORE giving a final count. Do not estimate — list them out, then count the list.
- DECOMPOSE complex sentences: "an immersive X with Y, enjoys Z" contains multiple distinct facts. Each could be the answer.
- Connect related facts across memories: if one says "nearby lake" and another says "Lake Tahoe is great for kayaking", the nearby lake IS Lake Tahoe. If one says "bought X in Paris", infer the country is France.

## Step 4: SELECT THE BEST ANSWER
- ALWAYS choose the MOST SPECIFIC detail available. A proper name, title, or number beats a generic description. Rate each candidate as HIGH specificity (name, title, number, specific activity) or LOW (generic description), and prefer HIGH.
- Report what someone actually DID, not what was offered or available to them. "Has not tried X yet" means X was NOT done — disqualify it. "Joined X" or "has done X" means it WAS done — prefer it.
- When multiple memories repeat the same generic fact, that repetition does NOT make it more correct than a single memory with a more specific answer.
- Photos depict what was IN the photo, not facts about someone's daily life. Prefer direct statements over photo descriptions for inferences.

## Step 5: TEMPORAL GROUNDING
These conversations took place around {reference_date}. All events occurred in 2022-2024.
- Calculate time relative to this date, NOT today. Never output 2025 or 2026.
- Use dates explicitly stated in memory text. Do not invent or estimate dates.
- When a question asks what someone "shared" or "mentioned" on a date, that date is when they TALKED about it — look for events shortly BEFORE that date.
- For "how long" questions, find the start and end dates explicitly, then compute the duration. Do not guess.

## Step 6: INCLUSION CHECK (for lists and counts)
If you found items during reasoning that you're tempted to exclude from your answer — STOP. Include them unless you have STRONG evidence they are wrong. The most common mistake is finding relevant items but then dropping them due to overly strict filtering. More items is better than fewer when there is supporting evidence.
- For counting: after enumerating, re-verify each item. Check for duplicates (same event described differently) and ensure you haven't missed items from memories late in the list.
- The question assumes something happened. Find WHAT happened, don't say nothing happened.

## Step 7: COMMIT AND ANSWER
Give a direct, specific answer. NEVER say "not specified", "not mentioned", "no record", or "the memories don't say" — if ANY memory contains relevant information, give the best answer from available evidence. No hedging, no caveats. If the question asks for a list, include ALL items found.
- NEVER generate specific names, titles, places, or dates that do not appear in any memory above. If no memory contains the specific detail the question asks for, answer with what the memories DO contain rather than guessing.

# Instructions

## Misc

1. Make reasonable deductions based on your memories. Memory shows store with a lot of working people -> store employs a lot of people
2. If a memory describes something recognizable (e.g., "romantic drama about memory and relationships"), you may name it (e.g., "Eternal Sunshine of the Spotless Mind").
3. Use domain knowledge to connect facts: a game exclusive to one platform implies ownership of that platform. An unnamed company deal can be linked to a previously expressed brand preference.

{memories}

Question: {question}

Work through Steps 1-7, then give your final answer after "ANSWER:".
"""

ANSWERER_MEMORY_LIMIT = 200


def _to_human_date(iso_str: str) -> str:
    """Convert ISO 8601 timestamp to human-readable date (e.g., 'May 7, 2023')."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return _datetime.strptime(iso_str[:26].rstrip("Z"), fmt.replace("%z", "")).strftime("%A, %B %d, %Y")
        except ValueError:
            continue
    return iso_str[:10]


def _format_user_profile(user_profile: dict) -> str:
    """Format a user profile dict as readable key-value pairs."""
    lines = ["## User Profile"]
    for key, value in user_profile.items():
        if value is None:
            continue
        display_key = key.replace("_", " ").title()
        if isinstance(value, list):
            if not value:
                continue
            display_value = ", ".join(str(v) for v in value)
        elif isinstance(value, str):
            if not value.strip():
                continue
            display_value = value
        else:
            display_value = str(value)
        lines.append(f"{display_key}: {display_value}")
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def get_answer_generation_prompt(
    question: str,
    search_results: list[dict[str, Any]],
    reference_date: str | None = None,
    user_profile: dict | None = None,
) -> str:
    """Build the answer generation prompt from search results.

    Shows top ANSWERER_MEMORY_LIMIT memories sorted chronologically.
    """
    if reference_date is None:
        reference_date = "2023"

    if not search_results:
        memories_text = "(No relevant memories found)"
    else:
        top_results = search_results[:ANSWERER_MEMORY_LIMIT]
        sorted_results = sorted(top_results, key=lambda x: x.get("created_at", ""))
        lines = ["The following memories are presented in chronological order (oldest to newest).", ""]
        for result in sorted_results:
            memory = result.get("memory", "")
            created_at = result.get("created_at", "")
            if created_at:
                date_str = _to_human_date(created_at)
                lines.append(f"({date_str}) {memory}")
            else:
                lines.append(f"(unknown date) {memory}")
        memories_text = "\n".join(lines)

    profile_section = ""
    if user_profile:
        profile_section = _format_user_profile(user_profile)
        if profile_section:
            profile_section = profile_section + "\n\n"

    return ANSWER_GENERATION_PROMPT.format(
        memories=profile_section + memories_text,
        question=question,
        reference_date=reference_date,
    )


# ===============================================================================
# JUDGE PROMPT
# ===============================================================================

JUDGE_SYSTEM_PROMPT = "You are evaluating conversational AI memory recall. Return JSON only with the format requested."

_EVIDENCE_CHUNK = """
## Evidence (actual conversation messages containing the answer)
{evidence_context}
"""

_EVIDENCE_RULE = """
5. **EVIDENCE SUPPORTS ANSWER**: If the evidence corroborates the generated answer, mark CORRECT — even when the generated answer diverges from the gold answer. The gold answer may be wrong or oversimplified; if the generated answer provides a more accurate or better-supported conclusion based on the evidence, that is acceptable. Use evidence only to ACCEPT answers, never to reject them more strictly.
"""

_EVIDENCE_WRONG_CLAUSE = " AND is not supported by evidence"

_JUDGE_TEMPLATE = """Label the generated answer as CORRECT or WRONG.
{evidence_section}
## Rules

1. **PARTIAL CREDIT**: If the generated answer includes AT LEAST ONE correct item from the gold answer's list, mark CORRECT. Getting 1 out of 2, 2 out of 4, etc. is always acceptable. Only mark WRONG if NONE of the gold answer items appear.

2. **PARAPHRASES COUNT**: Same concept in different words is CORRECT. "Chocolate raspberry tart" = "chocolate cake with raspberries". "Shelter meal service" = "volunteering at a homeless shelter". Judge semantic meaning, not wording.

3. **EXTRA DETAIL IS FINE**: A longer answer that includes the gold answer's key facts plus additional information is CORRECT. Never penalize for being more detailed or specific.

4. **DATE TOLERANCE**: Dates within 7 days of each other are CORRECT. Durations within 50% are CORRECT (e.g., "5 months" matches "six months"; "19 days" matches "two weeks"). Relative dates ("few days before November") match specific dates in the same window. A specific date (e.g., "February 2020") that is consistent with a vague reference (e.g., "a few years ago" relative to 2023) is CORRECT. Converting "last year" to the actual year (e.g., "2022" when conversations are in 2023) is CORRECT.
{evidence_rule}
5. **SEMANTIC OVERLAP**: Judge whether the generated answer addresses the same topic and captures the core idea of the gold answer. Different wording, phrasing, or level of detail should not result in WRONG if the underlying concept matches.

6. **FOCUS ON KNOWLEDGE, NOT WORDING**: The goal is to assess whether the system recalled the right fact. Minor differences in specificity, phrasing, or scope should not result in WRONG. Only mark WRONG when the generated answer demonstrates a genuinely different or incorrect understanding.

## ONLY mark WRONG if:
- The generated answer contains ZERO correct items from the gold answer{evidence_wrong_clause}
- The answer addresses a completely different topic

## Question
Question: {{question}}
Gold answer: {{answer}}
Generated answer: {{response}}

Return JSON with "reasoning" (one sentence) and "label" (CORRECT or WRONG). Do NOT include both labels."""


def _build_judge_prompt(evidence_context: str | None = None) -> str:
    """Build the judge prompt template, with or without evidence."""
    if evidence_context:
        prompt = _JUDGE_TEMPLATE.format(
            evidence_section=_EVIDENCE_CHUNK.format(evidence_context=evidence_context),
            evidence_rule=_EVIDENCE_RULE,
            evidence_wrong_clause=_EVIDENCE_WRONG_CLAUSE,
        )
        prompt = prompt.replace("\n5. **SEMANTIC OVERLAP", "\n6. **SEMANTIC OVERLAP")
        prompt = prompt.replace("\n6. **FOCUS ON KNOWLEDGE", "\n7. **FOCUS ON KNOWLEDGE")
    else:
        prompt = _JUDGE_TEMPLATE.format(
            evidence_section="",
            evidence_rule="",
            evidence_wrong_clause="",
        )
    return prompt


JUDGE_PROMPT = _build_judge_prompt(evidence_context=None)


def get_judge_prompt(
    category: int,
    question: str,
    answer: str,
    response: str,
) -> str:
    """Return the formatted unified judge prompt (no evidence)."""
    return JUDGE_PROMPT.format(question=question, answer=answer, response=response)


def get_judge_prompt_with_evidence(
    category: int,
    question: str,
    answer: str,
    response: str,
    evidence_context: str,
) -> str:
    """Return the formatted judge prompt with evidence context."""
    prompt = _build_judge_prompt(evidence_context=evidence_context)
    return prompt.format(question=question, answer=answer, response=response)


def preprocess_answer(category: int, answer: str) -> str:
    """Preprocess ground truth answer based on category.

    Category 3 (open-domain): use only the first part before semicolon.
    """
    if category == 3 and ";" in answer:
        return answer.split(";")[0].strip()
    return answer
