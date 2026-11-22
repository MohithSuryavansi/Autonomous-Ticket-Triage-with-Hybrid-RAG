"""
rag_pipeline/generation/title_generation.py

Generates concise, human-readable conversation/incident titles (3-6 words)
using the lightweight llama3.2:1b model via Ollama.
Runs before/during the start of the RAG pipeline for user queries.
"""
import re
from typing import Optional
import ollama

from rag_pipeline.config import TITLE_MODEL


_TITLE_PROMPT = """\
You are an expert IT incident triage coordinator.
Generate a concise, professional title (3 to 6 words maximum) summarizing the core issue or request in the user query.
Follow these rules strictly:
- Exactly 3 to 6 words.
- Do NOT use quotation marks, backticks, asterisks, or markdown.
- Do NOT add punctuation at the end.
- Do NOT include preamble or prefixes like "Title:" or "Summary:".
- Output ONLY the title text.

User Query: {query}
Title:"""


def _fallback_title(query: str) -> str:
    """Heuristic fallback if LLM title generation is unavailable."""
    clean = re.sub(r'[^\w\s-]', '', query).strip()
    words = clean.split()
    if not words:
        return "New Incident Investigation"
    return " ".join(words[:6]).title()


def clean_generated_title(raw_text: str, fallback_query: str) -> str:
    """Clean and sanitize LLM output to ensure a crisp title."""
    if not raw_text:
        return _fallback_title(fallback_query)

    # Remove prefixes like 'Title:', 'Incident:', etc.
    text = raw_text.strip()
    text = re.sub(r'^(Title|Incident|Summary|Subject)\s*:\s*', '', text, flags=re.IGNORECASE)
    # Remove quotes, backticks, asterisks, hashes
    text = re.sub(r'["\'`*#]', '', text).strip()
    text = text.rstrip('.!?,;:')

    # If the model produced multiple lines, take the first non-empty line
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        text = lines[0]

    words = text.split()
    if not words or len(words) < 2:
        return _fallback_title(fallback_query)

    if len(words) > 7:
        text = " ".join(words[:6])

    return text.strip()


def generate_title(query: str, model: str = TITLE_MODEL) -> str:
    """
    Generate a 3-6 word conversation title using llama3.2:1b.
    Falls back gracefully if Ollama is unreachable or errors.
    """
    if not query or not query.strip():
        return "New Incident Investigation"

    prompt = _TITLE_PROMPT.format(query=query.strip())
    try:
        resp = ollama.generate(
            model=model,
            prompt=prompt,
            options={
                "temperature": 0.1,
                "num_predict": 25,
                "top_p": 0.9,
            },
        )
        raw_output = resp.get("response", "").strip()
        return clean_generated_title(raw_output, query)
    except Exception as exc:
        print(f"[title_gen] ⚠️ llama3.2:1b title generation notice: {exc} — using fallback.")
        return _fallback_title(query)
