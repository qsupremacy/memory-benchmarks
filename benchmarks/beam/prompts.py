"""
BEAM Benchmark Prompt Templates
================================

Prompts for the BEAM benchmark (ICLR 2026):
- Answer generation from retrieved memories
- Rubric-based nugget judging (LLM-as-judge, 0.0/0.5/1.0 scoring)
- Fact extraction and event alignment for event_ordering (Kendall tau-b)

BEAM uses rubric-based scoring: each question has multiple rubric "nuggets"
scored independently. The question score is the average of all nugget scores.

10 memory ability types:
    abstention, contradiction_resolution, event_ordering, factual_qa,
    multi_hop, numerical_qa, preference_tracking, temporal_reasoning,
    world_knowledge, false_premise
"""

from __future__ import annotations

from datetime import datetime as _datetime
from typing import Any


# ===============================================================================
# QUESTION TYPES
# ===============================================================================

BEAM_QUESTION_TYPES = [
    "abstention",
    "contradiction_resolution",
    "event_ordering",
    "factual_qa",
    "multi_hop",
    "numerical_qa",
    "preference_tracking",
    "temporal_reasoning",
    "world_knowledge",
    "false_premise",
]

BEAM_QUESTION_TYPE_DESCRIPTIONS: dict[str, str] = {
    "abstention": "Withholding answers when evidence is absent from the conversation",
    "contradiction_resolution": "Detecting and reconciling inconsistent statements across dialogue turns",
    "event_ordering": "Reconstructing the chronological sequence of events and developments",
    "factual_qa": "Recalling specific entities, dates, numbers, and factual details",
    "multi_hop": "Integrating evidence scattered across non-adjacent dialogue segments",
    "numerical_qa": "Answering questions involving numeric reasoning over stored facts",
    "preference_tracking": "Adapting responses to evolving user preferences and personal choices",
    "temporal_reasoning": "Reasoning about explicit and implicit time relations, durations, and sequences",
    "world_knowledge": "Leveraging broad world knowledge to contextualize stored memories",
    "false_premise": "Identifying and correcting incorrect assumptions embedded in questions",
}


# ===============================================================================
# ANSWER GENERATION
# ===============================================================================

ANSWER_GENERATION_PROMPT = """\
You are an AI assistant with access to stored memories from prior conversations with a user.
Use these memories to answer the following question as accurately and completely as possible.

IMPORTANT RULES:
1. Scan ALL provided memories before answering -- do not stop after the first relevant one.
2. If multiple memories contain relevant information, combine and cross-reference them.
3. If the memories contain contradictory information, prefer the more recent one.
4. If the memories don't contain enough information to answer, say exactly: \
"I don't have enough information to answer this question."
5. For temporal questions: pay attention to dates and relative time references.
6. For ordering questions: present events in chronological order.
7. For preference questions: use the most recently stated preference.
8. Be specific and direct -- include exact names, dates, numbers, and details from the memories.
9. Do NOT invent or assume information that isn't in the memories.

QUESTION: {question}

RETRIEVED MEMORIES:
{memories}

ANSWER:"""


def _to_human_date(iso_str: str) -> str:
    """Convert ISO 8601 timestamp to human-readable date."""
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return _datetime.strptime(iso_str[:26].rstrip("Z"), fmt).strftime(
                "%A, %B %d, %Y"
            )
        except ValueError:
            continue
    return iso_str[:10]


def get_beam_answer_generation_prompt(
    question: str,
    memories: list[dict[str, Any] | str],
    top_k: int | None = None,
) -> str:
    """Build the prompt for generating an answer from retrieved memories.

    Args:
        question: The probing question to answer.
        memories: List of memory dicts (with at least ``"memory"`` key) or
            plain strings.
        top_k: If set, only use the first *top_k* memories.

    Returns:
        Fully formatted answer-generation prompt string.
    """
    if top_k is not None:
        memories = memories[:top_k]

    if not memories:
        memories_text = "(No memories available)"
    else:
        lines: list[str] = []
        for i, mem in enumerate(memories, 1):
            if isinstance(mem, dict):
                text = mem.get("memory", "")
                created_at = mem.get("created_at", "")
                if created_at:
                    date_str = _to_human_date(created_at)
                    lines.append(f"{i}. ({date_str}) {text}")
                else:
                    lines.append(f"{i}. {text}")
            else:
                lines.append(f"{i}. {mem}")
        memories_text = "\n".join(lines)

    return ANSWER_GENERATION_PROMPT.format(
        question=question,
        memories=memories_text,
    )


# ===============================================================================
# RUBRIC NUGGET JUDGE
# ===============================================================================

BEAM_JUDGE_SYSTEM_PROMPT = (
    "You are an expert evaluator assessing whether an AI assistant's response satisfies "
    "specific rubric criteria. You must be objective, fair, and consistent. "
    "Return ONLY valid JSON with the exact format requested."
)

BEAM_NUGGET_JUDGE_PROMPT = """\
Evaluate whether the following LLM response demonstrates compliance with the specified RUBRIC CRITERION.

QUESTION:
{question}

LLM RESPONSE:
{response}

RUBRIC CRITERION:
{nugget}

SCORING GUIDELINES:

First, determine whether the rubric criterion is a POSITIVE requirement (the response SHOULD \
include something) or a NEGATIVE constraint (the response SHOULD NOT include something).

**For POSITIVE requirements** (response should contain, mention, or demonstrate something):
- **1.0 (Complete Compliance)**: The required element is present, accurate, and complete. \
The response fully and clearly satisfies the rubric criterion.
- **0.5 (Partial Compliance)**: The required element is partially present, has minor \
inaccuracies, or is incomplete. The core intent is present but not fully realized.
- **0.0 (No Compliance)**: The required element is missing, incorrect, or the response is \
entirely off-topic / non-responsive.

**For NEGATIVE constraints** (response should NOT contain or should avoid something):
- **1.0 (Complete Compliance)**: The response is responsive to the question AND the prohibited \
element is absent.
- **0.5 (Partial Compliance)**: The response is responsive but contains a borderline or \
ambiguous reference to the prohibited element.
- **0.0 (No Compliance)**: The prohibited element is present in the response, OR the response \
is non-responsive (off-topic, refusal, empty).

**Compound statement handling**: If the rubric criterion contains "and" or commas connecting \
multiple required elements:
- All elements present and correct = 1.0
- Some (but not all) elements present and correct = 0.5
- No elements present or correct = 0.0

EVALUATION RULES:
1. **Semantic tolerance**: Paraphrases and synonyms are acceptable. The response does not need \
to use the exact same words as the rubric.
2. **Numeric and date equivalence**: Treat equivalent representations as identical. \
"$68,000" = "68k" = "sixty-eight thousand dollars". "2 years" = "24 months". Prefer normalized \
comparison for numbers, currencies, dates, and durations.
3. **Case / punctuation / whitespace tolerance**: Differences in capitalization, punctuation, \
and whitespace must be ignored when comparing content.
4. **Hedging tolerance**: Do not penalize hedging language ("I think", "probably", "it seems"), \
passive voice, or verbosity if the substantive content satisfies the rubric criterion.
5. **Style neutrality**: Do not penalize for tone, formatting, or length unless the rubric \
criterion specifically requires a particular format.
6. **Responsiveness**: If the LLM response is completely off-topic or refuses to answer, \
score 0.0 for all criteria.
7. **Independence**: Evaluate this criterion in isolation -- do not consider other rubric items.
8. **Specificity matters**: Vague or generic answers that could apply to any question score \
lower than specific, detailed answers.

STEP-BY-STEP EVALUATION:
Follow these steps in order:
1. **Understand the Requirement**: Read the rubric criterion and classify it as a positive \
requirement or a negative constraint.
2. **Parse Compound Statements**: If the criterion contains multiple sub-requirements joined \
by "and" or commas, identify each element separately.
3. **Check Compliance**: Compare the LLM response against each element, applying the tolerance \
rules above (semantic, numeric, case, hedging).
4. **Assign Score**: Use the appropriate scoring table (positive or negative) and \
compound-statement rule to determine the score.
5. **Provide Reasoning**: Write a concise explanation referencing which elements were or were \
not satisfied.

Return your evaluation as a JSON object with exactly two fields:
{{"score": <0.0 or 0.5 or 1.0>, "reason": "<one concise sentence explaining your score>"}}"""


def get_beam_nugget_judge_prompt(
    question: str,
    nugget: str,
    llm_response: str,
) -> str:
    """Build the prompt for judging a single rubric nugget.

    This follows BEAM's ``unified_llm_judge_base_prompt`` methodology.
    Each nugget is evaluated independently on a 3-point scale
    (0.0 / 0.5 / 1.0).

    Args:
        question: The probing question that was asked.
        nugget: The rubric criterion (nugget description) to evaluate.
        llm_response: The LLM-generated answer to evaluate against the nugget.

    Returns:
        Formatted judge prompt string. Expected JSON response format::

            {"score": 0.0|0.5|1.0, "reason": "one-sentence explanation"}
    """
    return BEAM_NUGGET_JUDGE_PROMPT.format(
        question=question,
        response=llm_response,
        nugget=nugget,
    )


# ===============================================================================
# EVENT ORDERING (Kendall tau-b helpers)
# ===============================================================================

FACT_EXTRACTION_PROMPT = """\
Extract all distinct events or facts mentioned in the following response, \
in the exact order they are presented. Return ONLY a JSON array of short event descriptions.

RESPONSE:
{response}

Return format: ["event 1 description", "event 2 description", ...]"""


def get_beam_fact_extraction_prompt(response: str) -> str:
    """Build a prompt to extract ordered facts/events for Kendall tau-b computation.

    The model should return a JSON array of event description strings
    in the order they appear in *response*.
    """
    return FACT_EXTRACTION_PROMPT.format(response=response)


EVENT_ALIGNMENT_PROMPT = """\
Given the following extracted event from an LLM response, determine which \
reference event it best corresponds to. Return ONLY a JSON object.

EXTRACTED EVENT:
{extracted_event}

REFERENCE EVENTS:
{events_list}

If the extracted event matches one of the reference events (even approximately or \
paraphrased), return the 0-based index. If it doesn't match any, return -1.

Return format: {{"index": <integer>, "reason": "<brief explanation>"}}"""


def get_beam_event_alignment_prompt(
    extracted_event: str,
    rubric_events: list[str],
) -> str:
    """Build a prompt to align an extracted event to the closest rubric event.

    Used for Kendall tau-b computation in event_ordering questions.

    Args:
        extracted_event: A single event extracted from the LLM response.
        rubric_events: The reference list of events from the rubric.

    Returns:
        Formatted alignment prompt. Expected JSON response::

            {"index": <int>, "reason": "<brief explanation>"}
    """
    events_list = "\n".join(f"{i}. {e}" for i, e in enumerate(rubric_events))
    return EVENT_ALIGNMENT_PROMPT.format(
        extracted_event=extracted_event,
        events_list=events_list,
    )
