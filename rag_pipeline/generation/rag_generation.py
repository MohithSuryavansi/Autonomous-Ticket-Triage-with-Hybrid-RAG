"""
generation/rag_generation.py

Assembles the top-8 reranked incidents into an enriched context prompt and
calls Qwen3:8b (via Ollama) to generate both a synthesised narrative answer
and a structured JSON routing payload.

Return value of generate_answer() is:
    (answer_text: str, structured: dict)

where `structured` contains:
    predicted_team          – the LLM-predicted handling team
    predicted_priority      – the LLM-predicted severity/priority
    routing_justification   – brief LLM reasoning for the above
    incident_attribution    – list of {id, team, urgency, impact} per retrieved incident
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import ollama

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS


# ── System prompt ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are AURA — an elite IT Incident Intelligence Analyst and Routing Specialist embedded in an \
enterprise SRE platform. You are given a user query and a set of relevant historical incident \
records, each enriched with the team that resolved it, its urgency, and its impact level.

═══════════════════════════════════════════════════════
YOUR MANDATORY TASKS
═══════════════════════════════════════════════════════

1.  Produce a COMPREHENSIVE, HIGHLY DETAILED incident analysis response structured into the
    following five clearly labelled sections. Each section MUST be substantive and thorough:

    ── SECTION 1: INCIDENT OVERVIEW ──────────────────────────────────────────────────────────
    Summarise what kind of incident is being described. Include: the apparent symptom pattern,
    what category of failure this likely belongs to, and which systems / components are involved.
    Cite relevant historical incident IDs (e.g. INC001, INC003) to anchor your observations.

    ── SECTION 2: LIKELY ROOT CAUSES ────────────────────────────────────────────────────────
    Analyse the underlying root causes based on patterns from the retrieved incidents. List
    EACH probable cause as a numbered sub-point with a brief technical explanation. Distinguish
    between primary causes and contributing factors where possible.

    ── SECTION 3: INVESTIGATION CHECKLIST ───────────────────────────────────────────────────
    Provide a step-by-step numbered checklist of exactly WHERE and HOW to look for evidence:
    - Specific log files, dashboards, metrics, or monitoring tools to check
    - Exact commands, queries, or API calls the on-call engineer should run
    - Alert thresholds, error codes, or signatures that confirm the diagnosis

    ── SECTION 4: RESOLUTION STRATEGY ──────────────────────────────────────────────────────
    Provide a numbered, ordered set of resolution steps from immediate triage through to full
    remediation. Each step must be actionable and specific. Include:
    - Immediate containment / mitigation actions (to stop the bleeding)
    - Short-term fix steps (to restore service)
    - Long-term remediation steps (to prevent recurrence)

    ── SECTION 5: PREVENTION & RECOMMENDATIONS ──────────────────────────────────────────────
    Based on historical patterns, recommend systemic improvements: configuration changes,
    monitoring additions, runbook updates, or architectural changes that would reduce recurrence.

2.  Based on the patterns in the historical incidents, determine the best routing and severity:
    - The most appropriate team to handle / forward this new issue.
    - The predicted priority/severity for this issue (use: 1 - Critical / 2 - High / 3 - Moderate / 4 - Low).
    - A one-sentence justification for your routing decision.

3.  Build an attribution list noting which team handled each retrieved incident.

═══════════════════════════════════════════════════════
MANDATORY OUTPUT FORMAT
═══════════════════════════════════════════════════════
You MUST produce BOTH sections below, in this exact order. Do NOT omit either section.

[ANSWER]
## 🔍 Incident Overview
<your detailed incident overview — minimum 3 sentences>

## 🧠 Likely Root Causes
<numbered list of root causes with technical explanations>

## 🔎 Investigation Checklist
<numbered step-by-step investigation guide with specific commands, logs, and metrics>

## ⚙️ Resolution Strategy
<numbered ordered resolution steps: containment → fix → remediation>

## 🛡️ Prevention & Recommendations
<systemic improvement recommendations>
[/ANSWER]

<structured>
{
  "predicted_team": "<team name>",
  "predicted_priority": "<e.g. 1 - Critical>",
  "routing_justification": "<one sentence>",
  "incident_attribution": [
    {"id": "<incident id>", "team": "<assignment_group>", "urgency": "<urgency>", "impact": "<impact>"},
    ...
  ]
}
</structured>

═══════════════════════════════════════════════════════
RULES
═══════════════════════════════════════════════════════
- Ground your analysis in the provided historical incidents — cite incident IDs throughout.
- Do NOT invent incident IDs or facts not present in the context.
- If context is insufficient for routing, set predicted_team and predicted_priority to "Unknown".
- Always output the <structured> block even if some fields are Unknown.
- Be comprehensive. The on-call engineer reading this must have everything they need to act.
"""


# ── Formatters ─────────────────────────────────────────────────────────────────

def _format_incident(incident: Dict, rank: int) -> str:
    """Format a single incident into a numbered context block for the prompt."""
    meta = incident.get("metadata", {})
    return (
        f"--- Incident {rank}: {incident.get('id', '')} ---\n"
        f"Short Description: {meta.get('short_description', '')}\n"
        f"Description:       {meta.get('description', '')}\n"
        f"Category:          {meta.get('category', '')}\n"
        f"Urgency:           {meta.get('urgency', '')} | "
        f"Impact:            {meta.get('impact', '')}\n"
        f"Assignment Group:  {meta.get('assignment_group', '')}\n"
        f"Affected Component:{meta.get('affected_component', '')}\n"
        f"Resolution:        {meta.get('resolution', '')}\n"
    )


def _extract_historical_context(incidents: List[Dict]) -> str:
    """
    Extract key metadata from every retrieved incident as a compact summary
    table. This is injected near the top of the user message so the LLM can
    reason about historical routing patterns before writing its answer.
    """
    lines = ["HISTORICAL ROUTING CONTEXT (extracted from retrieved incidents):"]
    lines.append(f"{'#':<4} {'Incident ID':<14} {'Team':<35} {'Urgency':<12} {'Impact'}")
    lines.append("-" * 90)
    for i, inc in enumerate(incidents, 1):
        meta = inc.get("metadata", {})
        lines.append(
            f"{i:<4} {inc.get('id', ''):<14} "
            f"{meta.get('assignment_group', 'Unknown'):<35} "
            f"{meta.get('urgency', ''):<12} "
            f"{meta.get('impact', '')}"
        )
    return "\n".join(lines)


# ── Output parser ──────────────────────────────────────────────────────────────

_ANSWER_RE = re.compile(r"\[ANSWER\](.*?)\[/ANSWER\]", re.DOTALL)
_STRUCT_RE  = re.compile(r"<structured>(.*?)</structured>", re.DOTALL)

_EMPTY_STRUCTURED: Dict = {
    "predicted_team": "",
    "predicted_priority": "",
    "routing_justification": "",
    "incident_attribution": [],
}


def _parse_structured_output(raw: str) -> Tuple[str, Dict]:
    """
    Extract the narrative answer and structured JSON from the LLM response.

    Returns:
        (answer_text, structured_dict)

    Falls back gracefully if either section is missing or JSON is malformed.
    """
    # Extract narrative answer
    answer_match = _ANSWER_RE.search(raw)
    if answer_match:
        answer_text = answer_match.group(1).strip()
    else:
        # Fallback: strip the structured block and use the rest as the answer
        answer_text = _STRUCT_RE.sub("", raw).strip()

    # Extract and parse structured JSON
    struct_match = _STRUCT_RE.search(raw)
    if struct_match:
        try:
            structured = json.loads(struct_match.group(1).strip())
        except json.JSONDecodeError as exc:
            print(f"[rag_generation] ⚠️  JSON parse error in structured block: {exc}")
            structured = dict(_EMPTY_STRUCTURED)
    else:
        print("[rag_generation] ⚠️  No <structured> block found in LLM response.")
        structured = dict(_EMPTY_STRUCTURED)

    # Ensure required keys exist
    for key, default in _EMPTY_STRUCTURED.items():
        structured.setdefault(key, default)

    return answer_text, structured


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_answer(
    query: str,
    reranked_incidents: List[Dict],
) -> Tuple[str, Dict]:
    """
    Build the enriched context + user message and generate an LLM response.

    Args:
        query:               The original user query.
        reranked_incidents:  Top-N incident dicts from the reranker.

    Returns:
        (answer_text, structured_dict) where structured_dict contains
        predicted_team, predicted_priority, routing_justification,
        and incident_attribution.
    """
    historical_table = _extract_historical_context(reranked_incidents)
    context_blocks   = "\n".join(
        _format_incident(inc, i) for i, inc in enumerate(reranked_incidents, 1)
    )

    user_message = (
        f"{historical_table}\n\n"
        f"FULL INCIDENT CONTEXT:\n{context_blocks}\n\n"
        f"USER QUESTION: {query}\n\n"
        f"Respond strictly following the output format described in the system prompt."
    )

    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        options={
            "temperature": LLM_TEMPERATURE,
            "num_predict": LLM_MAX_TOKENS,
        },
    )

    raw = response["message"]["content"]
    return _parse_structured_output(raw)
