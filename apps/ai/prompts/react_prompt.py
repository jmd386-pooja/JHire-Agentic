# ai/prompts/react_prompt.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import json

SYSTEM_HEADER = """You are a ReAct-style planner. Think step-by-step, choose a tool, observe, repeat, then finish.
You have at most {max_steps} steps. Follow this strict output format each step:

Thought: <your brief thought>
Action: {{"tool": "<tool_name>", "args": {{...}}}}

After a tool runs, you'll receive:
Observation: {{"ok": true|false, ...}}

When you are done, finish exactly with:
Action: {{"tool": "Finish", "args": {{"answer": "<final answer>","evidence": []}}}}
"""

def _render_tools(tools: Dict[str, Dict[str, Any]]) -> str:
    lines: List[str] = []
    for name, spec in (tools or {}).items():
        desc = (spec.get("description") or "").strip()
        schema = spec.get("schema") or {}
        # schema gets inserted as text; it can include braces safely
        schema_text = json.dumps(schema, ensure_ascii=False)
        lines.append(f"- {name}: {desc}\n  args_schema: {schema_text}")
    return "\n".join(lines) if lines else "(no tools registered)"

def _render_reflections(reflections: Optional[List[str]]) -> str:
    if not reflections:
        return ""
    items = "\n".join(f"- {r}" for r in reflections if r)
    return f"\nReflections to keep in mind:\n{items}\n"

def make_react_prompt(
    goal: str,
    tools: Dict[str, Dict[str, Any]],
    reflections: Optional[List[str]] = None,
    context: Optional[str] = None,
    max_steps: int = 7,
) -> str:
    # IMPORTANT: Use a template with {{ }} for literal JSON braces so .format only substitutes max_steps
    system = SYSTEM_HEADER.format(max_steps=max_steps)

    tools_block = _render_tools(tools)
    reflections_block = _render_reflections(reflections)

    transcript = (context or "").strip()
    if transcript:
        transcript = f"\nPrevious steps so far:\n{transcript}\n"

    prompt = (
        f"{system}\n\n"
        f"Your goal:\n{goal}\n\n"
        f"Available tools (name, description, and JSON args schema):\n{tools_block}\n"
        f"{reflections_block}"
        f"{transcript}"
        "Now produce the next step. Remember to output exactly two lines per step:\n"
        "Thought: ...\n"
        "Action: {\"tool\": \"...\", \"args\": {...}}\n"
    )
    return prompt
