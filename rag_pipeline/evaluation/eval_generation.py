"""
evaluation/eval_generation.py

Stripped-down answer generator for RAGAS evaluation.
Uses qwen3:8b (via Ollama) with a plain-text prompt that removes all
frontend UI formatting (emoji, markdown headers, [ANSWER] tags).

Returns:
    answer_text (str)   — clean prose answer for RAGAS scoring
    structured  (dict)  — routing metadata dict
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import ollama

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rag_pipeline.config import LLM_TEMPERATURE, LLM_MAX_TOKENS

GENERATION_MODEL = "qwen3:8b"
EVALUATION_MODEL = "llama3.1:latest"

_EVAL_SYSTEM_PROMPT = """\
You are an expert IT incident analyst evaluating against historical knowledge base runbooks. \
You are given a user query describing an IT incident and a set of relevant historical incident records.

YOUR TASKS:
1. Write a focused, strictly grounded incident resolution as clean plain text (no emoji, no markdown headers):
   - Root Cause: Underlying cause identified from the historical incident records (cite incident IDs)
   - Resolution: Technical remediation procedure based strictly on the retrieved historical resolutions

2. Determine routing and severity:
   - Most appropriate team: Network Ops or IT Support
   - Predicted priority: 1 - Critical / 2 - High / 3 - Moderate / 4 - Low
   - One-sentence routing justification

3. Attribution list: which team handled each retrieved incident.

OUTPUT FORMAT - produce BOTH sections in this exact order:

[ANSWER]
Root Cause: <cite incident IDs and explain underlying technical cause found in the historical records>
Resolution: <step-by-step remediation procedure directly derived from the retrieved incident resolutions>
[/ANSWER]

<structured>
{
  "predicted_team": "<team name>",
  "predicted_priority": "<e.g. 2 - High>",
  "routing_justification": "<one sentence>",
  "incident_attribution": [
    {"id": "<incident id>", "team": "<assignment_group>", "urgency": "<urgency>", "impact": "<impact>"}
  ]
}
</structured>

STRICT GROUNDING RULES:
- Focus on the primary, highest-relevance matching historical incident (Candidate 1 is usually the strongest match). Ground your Root Cause and Resolution directly in that primary incident's technical facts rather than blending or switching to peripheral tickets.
- Ground all findings strictly in the provided historical incidents. Cite incident IDs.
- Do NOT repeat or echo user-specific office locations, company names, or hypothetical premises in the [ANSWER].
- Use only concrete parameters, diagnostic commands, and technical facts directly stated in the retrieved incidents. Avoid generic placeholders like <remote_ip>.
- Every diagnostic check, root cause claim, and resolution step MUST be directly supported by the retrieved incident contexts.
- Do NOT invent external commands, unmentioned tools, or generic advice not documented in the retrieved tickets.
- If context is insufficient, state only what is directly supported by the historical records.
- Always output the <structured> block.
"""

_ANSWER_RE = re.compile(r"\[ANSWER\](.*?)\[/ANSWER\]", re.DOTALL)
_STRUCT_RE  = re.compile(r"<structured>(.*?)</structured>", re.DOTALL)
_THINK_RE   = re.compile(r"<think>.*?</think>", re.DOTALL)

_EMPTY_STRUCTURED: Dict = {
    "predicted_team": "",
    "predicted_priority": "",
    "routing_justification": "",
    "incident_attribution": [],
}


def _format_incident(incident: Dict, rank: int) -> str:
    m = incident.get("metadata", {})
    return (
        f"--- Incident {rank}: {incident.get('id', '')} ---\n"
        f"Short Description: {m.get('short_description', '')}\n"
        f"Description:       {m.get('description', '')}\n"
        f"Category:          {m.get('category', '')}\n"
        f"Urgency: {m.get('urgency', '')} | Impact: {m.get('impact', '')}\n"
        f"Team:              {m.get('assignment_group', '')}\n"
        f"Component:         {m.get('affected_component', '')}\n"
        f"Resolution:        {m.get('resolution', '')}\n"
    )


def _extract_historical_context(incidents: List[Dict]) -> str:
    lines = ["HISTORICAL ROUTING CONTEXT (from retrieved incidents):"]
    lines.append(f"{'#':<4} {'Incident ID':<14} {'Team':<35} {'Urgency':<12} Impact")
    lines.append("-" * 90)
    for i, inc in enumerate(incidents, 1):
        m = inc.get("metadata", {})
        lines.append(
            f"{i:<4} {inc.get('id', ''):<14} "
            f"{m.get('assignment_group', 'Unknown'):<35} "
            f"{m.get('urgency', ''):<12} "
            f"{m.get('impact', '')}"
        )
    return "\n".join(lines)


def _parse_output(raw: str) -> Tuple[str, Dict]:
    raw = _THINK_RE.sub("", raw).strip()
    answer_match = _ANSWER_RE.search(raw)
    answer_text = answer_match.group(1).strip() if answer_match else _STRUCT_RE.sub("", raw).strip()
    struct_match = _STRUCT_RE.search(raw)
    if struct_match:
        try:
            structured = json.loads(struct_match.group(1).strip())
        except json.JSONDecodeError as exc:
            print(f"[eval_generation] WARNING JSON parse error: {exc}")
            structured = dict(_EMPTY_STRUCTURED)
    else:
        structured = dict(_EMPTY_STRUCTURED)
    for key, default in _EMPTY_STRUCTURED.items():
        structured.setdefault(key, default)
    return answer_text, structured


def generate_eval_answer(query: str, reranked_incidents: List[Dict]) -> Tuple[str, Dict]:
    """
    Generate a clean evaluation answer using qwen3:8b.

    Args:
        query:               Preprocessed incident query string.
        reranked_incidents:  Top-N incident dicts from the cross-encoder reranker.

    Returns:
        (answer_text, structured_dict)
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
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": _EVAL_SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        options={"temperature": LLM_TEMPERATURE, "num_predict": LLM_MAX_TOKENS},
    )
    raw = response["message"]["content"]
    return _parse_output(raw)


def unload_generation_model() -> None:
    """Signal Ollama to evict qwen3:8b from VRAM immediately."""
    print(f"[eval_generation] Unloading {GENERATION_MODEL} from VRAM...")
    try:
        ollama.generate(model=GENERATION_MODEL, prompt="", keep_alive=0)
        print(f"[eval_generation] {GENERATION_MODEL} unloaded successfully.")
    except Exception as exc:
        print(f"[eval_generation] WARNING: Could not signal unload: {exc}")


if __name__ == "__main__":
    print("eval_generation.py — smoke test")
    mock = [{
        "id": "INC001",
        "metadata": {
            "short_description": "DB timeout",
            "description": "JDBC pool exhausted during peak hours.",
            "category": "Database", "urgency": "2", "impact": "2",
            "assignment_group": "Database Admin",
            "affected_component": "App-DB Pool",
            "resolution": "Increased pool size, added validation.",
        },
        "document": "",
    }]
    ans, struct = generate_eval_answer("Production DB showing intermittent connection timeouts.", mock)
    print("ANSWER (first 400 chars):", ans[:400])
    print("STRUCTURED:", json.dumps(struct, indent=2))
