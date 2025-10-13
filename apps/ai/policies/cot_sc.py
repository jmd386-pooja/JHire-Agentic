# ai/policies/cot_sc.py
from __future__ import annotations
from typing import List, Tuple, Callable, Optional, Dict, Any
import os
import re
from collections import Counter

try:
    import google.generativeai as genai  # pip install google-generativeai
except Exception:  # pragma: no cover
    genai = None


def _norm(txt: str) -> str:
    txt = txt or ""
    txt = txt.strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def _evidence_score(answer: str, evidence: List[Any]) -> int:
    """
    Simple tie-break heuristic:
      +1 for each evidence URL that appears in the answer text
      +1 for each domain that appears (e.g., example.com)
    """
    score = 0
    if not answer or not evidence:
        return 0
    txt = answer.lower()
    for ev in evidence:
        if isinstance(ev, str):
            url = ev.lower()
            if url in txt:
                score += 1
            # domain match
            m = re.search(r"https?://([^/]+)/?", url)
            if m and m.group(1) in txt:
                score += 1
        elif isinstance(ev, dict) and "sql" in ev:
            # bonus if answer mentions 'SQL' when we used DB
            if "sql" in txt or "query" in txt:
                score += 1
    return score


def _render_transcript(steps: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for st in steps:
        thought = (st.get("thought") or "").strip()
        action = st.get("action") or {}
        obs = st.get("observation") or {}
        if thought:
            lines.append(f"Thought: {thought}")
        if action:
            lines.append(f"Action: {action}")
        if obs:
            lines.append(f"Observation: {obs}")
    return "\n".join(lines)


def _make_prompt(goal: str, transcript: str, evidence: List[Any]) -> str:
    ev_lines: List[str] = []
    for ev in evidence[:8]:
        if isinstance(ev, str):
            ev_lines.append(f"- {ev}")
        elif isinstance(ev, dict) and "sql" in ev:
            ev_lines.append(f"- SQL: {ev['sql'][:180]}")
    ev_block = "\n".join(ev_lines) or "(none)"

    return (
        "You are a finalizer model. Produce ONE concise, grounded answer.\n"
        "Use the evidence when present; do not invent facts. If evidence is weak, say so.\n"
        "Do not output chain-of-thought; just the final answer.\n\n"
        f"Goal:\n{goal}\n\n"
        f"Transcript (last steps):\n{transcript}\n\n"
        f"Evidence (URLs/SQL):\n{ev_block}\n\n"
        "Final answer:"
    )


def make_gemini_cot_sc(n: int = 5, temperature: float = 0.7, model_name_env: str = "GEMINI_COT_MODEL") -> Callable[[Any], str]:
    """
    Returns a function(state)->str suitable for react_agent.run(..., planner_cot_sc=...).
    Uses Gemini to sample N final answers and majority-votes them.
    Env: GOOGLE_API_KEY or GEMINI_API_KEY, optional GEMINI_COT_MODEL (default 'gemini-1.5-flash').
    """
    def _fn(state: Any) -> str:
        if genai is None:
            # graceful degradation
            snippets: List[str] = []
            for st in state.steps[-3:]:
                obs = st.observation or {}
                if isinstance(obs, dict):
                    if "text" in obs and isinstance(obs["text"], str):
                        snippets.append(obs["text"][:400])
                    if "rows" in obs and isinstance(obs["rows"], list):
                        snippets.append(f"DB rows (sample): {obs['rows'][:2]}")
            body = " | ".join(snippets) or "No reliable evidence gathered."
            return f"(Fallback) Based on partial evidence: {body}"

        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            # degrade to the simple fallback
            snippets: List[str] = []
            for st in state.steps[-3:]:
                obs = st.observation or {}
                if isinstance(obs, dict):
                    if "text" in obs and isinstance(obs["text"], str):
                        snippets.append(obs["text"][:400])
                    if "rows" in obs and isinstance(obs["rows"], list):
                        snippets.append(f"DB rows (sample): {obs['rows'][:2]}")
            body = " | ".join(snippets) or "No reliable evidence gathered."
            return f"(Fallback) Based on partial evidence: {body}"

        genai.configure(api_key=key)
        model_name = os.getenv(model_name_env, "gemini-2.0-flash-thinking-exp")
        model = genai.GenerativeModel(model_name)

        goal = getattr(state, "goal", "")
        # Build a lightweight transcript from the last steps
        steps_for_prompt = [
            {
                "thought": s.thought,
                "action": {"tool": s.action.tool, "args": s.action.args},
                "observation": s.observation,
            }
            for s in getattr(state, "steps", [])[-6:]
        ]
        transcript = _render_transcript(steps_for_prompt)
        evidence = list(getattr(state, "evidence", []))

        prompt = _make_prompt(goal, transcript, evidence)

        # Sample N answers
        samples: List[str] = []
        for _ in range(max(1, int(n))):
            resp = model.generate_content(
                prompt,
                generation_config={
                    "temperature": float(temperature),
                    "top_p": 0.95,
                    "top_k": 40,
                },
            )
            txt = getattr(resp, "text", "") or ""
            if not txt and getattr(resp, "candidates", None):
                parts = []
                for cand in resp.candidates:
                    for p in getattr(cand, "content", {}).parts or []:
                        if getattr(p, "text", None):
                            parts.append(p.text)
                txt = "\n".join(parts).strip()
            if txt:
                samples.append(txt.strip())

        if not samples:
            return "I couldn't form a confident final answer from the available evidence."

        # Majority vote (by normalized text); if tie, pick the one that references evidence best
        counts = Counter(_norm(s) for s in samples)
        winner_norm, _ = counts.most_common(1)[0]
        tied_norms = [k for k, v in counts.items() if v == counts[winner_norm]]

        if len(tied_norms) == 1:
            # return the first original sample that matches the winner_norm
            for s in samples:
                if _norm(s) == winner_norm:
                    return s
            return samples[0]

        # tie-break by evidence mention score
        best: Tuple[int, str] = (-1, samples[0])
        for s in samples:
            if _norm(s) in tied_norms:
                sc = _evidence_score(s, evidence)
                if sc > best[0]:
                    best = (sc, s)
        return best[1]

    return _fn
