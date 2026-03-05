"""
LLM-backed research-focused summaries for notes.

Given a paper (title/abstract/metadata) and config, build a structured
research summary covering:
- subfield / problem definition
- motivation
- what is solved / main contributions
- high-level method overview

Language is configurable via config.summarize.language (default: English).
This module is intentionally conservative: failures to call the LLM should
never break the main pipeline; callers can treat a None/empty string result
as "no extra summary available".
"""

from __future__ import annotations

import os
from typing import Optional

import requests

from paper_agent.core.config import Config
from paper_agent.core.models import Paper


def _detect_language_label(lang: str) -> tuple[str, str]:
    """
    Map config language code/string to:
    - language name for instructions
    - section heading to use in the note
    """
    v = (lang or "").lower()
    if v.startswith("zh"):
        return "Chinese", "研究视角总结"
    if v.startswith("ja"):
        return "Japanese", "Research-focused summary"
    if v.startswith("de"):
        return "German", "Research-focused summary"
    # Default: English
    return "English", "Research-focused summary"


def _build_research_prompt(paper: Paper, why: str | None, config: Config) -> str:
    """Construct the research-structured prompt for the LLM."""
    language_name, _ = _detect_language_label(config.summarize.language)

    keyphrases = ", ".join(config.interests.keyphrases) or "N/A"
    include_kw = ", ".join(config.direction.include_keywords) or "N/A"
    categories = ", ".join(paper.categories) or "N/A"

    why_text = why or "—"

    return f"""
You are a research assistant for machine learning papers.
Read the following paper metadata and produce a concise, structured summary
for a researcher. Answer strictly in {language_name}.

Paper metadata:
- Title: {paper.title}
- Abstract: {paper.summary}
- Authors: {", ".join(paper.authors) or "N/A"}
- Categories: {categories}
- arXiv ID: {paper.id}
- arXiv URL: {paper.link_abs}
- Matched keyphrases (user interests): {keyphrases}
- Direction include_keywords: {include_kw}
- Existing why_this_paper (selection rationale): {why_text}

Please output the summary in plain text with the following numbered sections:

1. Subfield and problem definition
- State the specific research subfield this paper belongs to (e.g., class-incremental continual learning, multi-task representation learning, etc.).
- Give a 1–2 sentence precise definition of the main problem being addressed (what setting, what constraints).

2. Motivation
- List 1–3 concrete limitations of existing work that the paper highlights.
- Explain what property or metric the paper aims to improve (e.g., stability-plasticity trade-off, sample efficiency, inference cost).

3. What the paper claims to solve
- Summarize 2–4 main contributions, each as "problem → idea" if possible.
- Clarify whether contributions are about data, model architecture, training strategy, inference strategy, or evaluation protocol.

4. Method overview (high level)
- Describe the core method as 3–6 ordered steps (input → processing modules → output).
- Highlight the 1–2 design choices that most directly address the motivation (e.g., a specific loss, memory mechanism, routing/gating, etc.).

5. Relevance for the user
- In 1–2 sentences, explain why this paper could be useful for someone interested in the user's keyphrases and queries (e.g., continual learning with routing/gating, mixture-of-experts, etc.).

If the metadata is insufficient to answer a specific bullet reliably, explicitly say
"Information insufficient to judge" for that bullet instead of guessing.
"""


def _call_openai_chat(prompt: str, model: str, timeout_seconds: int) -> Optional[str]:
    """
    Minimal OpenAI Chat Completions call via requests.
    Uses OPENAI_API_KEY from the environment.
    Returns None on any failure.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise research assistant for machine learning papers."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content", "")
        return content.strip() or None
    except Exception:
        return None


def build_research_summary(paper: Paper, why: str | None, config: Config) -> Optional[tuple[str, str]]:
    """
    Generate a research-focused summary for a paper using the configured LLM.

    Returns:
        (heading, body) if successful, or None if summarization is disabled
        or the provider cannot be used.
    """
    summ_cfg = config.summarize
    if not getattr(summ_cfg, "enabled", True):
        return None

    # Optional separate switch so users can enable one-liner for Slack but
    # turn off research summaries, and vice versa.
    if not getattr(summ_cfg, "research_summary_enabled", True):
        return None

    language_name, heading = _detect_language_label(summ_cfg.language)

    prompt = _build_research_prompt(paper, why, config)

    body: Optional[str] = None
    provider = (summ_cfg.provider or "openai").lower()
    timeout = getattr(config.advanced, "request_timeout_seconds", 30)

    if provider == "openai":
        body = _call_openai_chat(prompt, summ_cfg.model, timeout)
    else:
        # Unknown provider; caller should treat as "no extra summary".
        return None

    if not body:
        return None

    # Heading is language-dependent; body is already in the requested language.
    return heading, body


__all__ = ["build_research_summary"]

