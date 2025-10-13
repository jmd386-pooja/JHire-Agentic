from __future__ import annotations
"""
react_agent.py
--------------
A universal ReAct loop that interleaves:
  Thought -> Action(JSON) -> Observation -> ... -> Finish

This file is framework-agnostic and expects a planner callable that, given the
current state and a prompt string, returns:
    (thought_text: str, action_dict: {"tool": str, "args": dict})

Key features:
- Dynamic tools from tools_registry.load_all_tools
- JSON-schema style arg validation (lightweight)
- Approval middleware (ai.policies.approvals.requires_approval)
- Error-as-Observation (never raise to the planner)
- Step caps and loop detection
- Evidence-before-finish policy (optional)
- CoT-SC fallback hook
- Simple trajectory logging structure (return value)
"""

from dataclasses import dataclass, field
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict
import json
import re


# --------------------
# Local imports (adjust if needed)
# --------------------
try:
    from prompts.react_prompt import make_react_prompt
except Exception:
    make_react_prompt = None  # type: ignore

try:
    from tools_registry import load_all_tools, ToolSpec
except Exception:
    load_all_tools = None  # type: ignore
    ToolSpec = dict  # type: ignore


# --------------------
# Data structures
# --------------------
@dataclass
class Action:
    tool: str
    args: Dict[str, Any]


@dataclass
class StepRecord:
    thought: str
    action: Action
    observation: Dict[str, Any]


@dataclass
class AgentState:
    goal: str
    steps: List[StepRecord] = field(default_factory=list)
    evidence: List[Any] = field(default_factory=list)
    confidence: float = 0.0
    max_steps: int = 7  # step cap (policy)
    tools: Dict[str, ToolSpec] = field(default_factory=dict)
    context: Optional[str] = None
    reflections: Optional[List[str]] = None
    intent_hint: Optional[str] = None
    finished: bool = False
    final_answer: Optional[str] = None
    error: Optional[str] = None

class ToolSpec(TypedDict):
    name: str
    description: str
    schema: Dict[str, Any]
    runner: Callable[[Dict[str, Any]], Dict[str, Any]]


# --------------------
# Utility helpers
# --------------------
def _light_jsonschema_validate(args: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
    """
    Lightweight validator: checks required fields and basic type matches for "string",
    "integer", "number", "boolean", "array", "object". Returns None if ok, else error str.
    """
    if not isinstance(args, dict):
        return "args_must_be_object"

    required = schema.get("required", [])
    props = schema.get("properties", {})

    for key in required:
        if key not in args:
            return f"missing_required:{key}"

    def _match(expected: str, value: Any) -> bool:
        if expected == "string":
            return isinstance(value, str)
        if expected == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected == "boolean":
            return isinstance(value, bool)
        if expected == "array":
            return isinstance(value, list)
        if expected == "object":
            return isinstance(value, dict)
        # Unknown types: pass through
        return True

    for key, spec in props.items():
        if key in args:
            typ = spec.get("type")
            if typ and not _match(typ, args[key]):
                return f"type_mismatch:{key}:{typ}"

    # additionalProperties
    if schema.get("additionalProperties") is False:
        for k in args.keys():
            if k not in props:
                return f"unexpected_property:{k}"

    return None


def _render_transcript_for_llm(state: AgentState) -> str:
    """Render partial transcript for the planner (Thought/Action/Observation)."""
    lines: List[str] = []
    for st in state.steps:
        lines.append(f"Thought: {st.thought.strip()}")
        # One-line JSON for Action
        action_json = json.dumps({"tool": st.action.tool, "args": st.action.args}, ensure_ascii=False)
        lines.append(f"Action: {action_json}")
        # Compact Observation (truncate long strings)
        obs = st.observation
        obs_compact = {}
        for k, v in (obs or {}).items():
            if isinstance(v, str) and len(v) > 800:
                obs_compact[k] = v[:800] + "... [truncated]"
            else:
                obs_compact[k] = v
        obs_json = json.dumps(obs_compact, ensure_ascii=False)
        lines.append(f"Observation: {obs_json}")
    return "\n".join(lines)


def _looks_like_loop(thoughts: List[str]) -> bool:
    """
    Returns True if the last two thoughts look near-duplicate.
    Heuristic: normalize to alphanumerics+spaces, compute token overlap.
    """
    if len(thoughts) < 2:
        return False
    a, b = thoughts[-1].lower(), thoughts[-2].lower()

    # Strip punctuation/noise
    import re as _re
    a = _re.sub(r"[\W_]+", " ", a).strip()
    b = _re.sub(r"[\W_]+", " ", b).strip()
    if not a or not b:
        return False

    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return False

    # Jaccard overlap over unique tokens
    overlap = len(sa & sb) / max(1, len(sa | sb))
    return overlap > 0.8  # tune threshold as desired


# --------------------
# Core functions
# --------------------
def plan_with_llm(
    state: AgentState,
    planner: Callable[[AgentState, Dict[str, ToolSpec], str], Tuple[str, Dict[str, Any]]],
) -> Tuple[str, Dict[str, Any]]:
    """
    Build the prompt and call the injected planner. The planner must return:
        thought_text, action_dict (with keys 'tool' and 'args')
    """
    if make_react_prompt is None:
        raise RuntimeError("make_react_prompt not available. Ensure prompts.react_prompt is importable.")

    tool_specs = state.tools
    prompt = make_react_prompt(
        goal=state.goal,
        tools=tool_specs,
        reflections=state.reflections,
        context=_render_transcript_for_llm(state),
        max_steps=state.max_steps,
    )
    thought, action = planner(state, tool_specs, prompt)
    if not isinstance(action, dict) or "tool" not in action or "args" not in action:
        raise ValueError("planner must return (thought:str, action:{'tool':..., 'args':{...}})")
    return thought, action


def execute_action(action: Dict[str, Any], tools: Dict[str, ToolSpec]) -> Dict[str, Any]:
    """
    Validate, approval-check, and run a tool. Return an Observation dict, never raise.

    Approval policy:
      - If ai.policies.approvals.requires_approval(tool) is True and action.args lacks `_approved: True`,
        return {"ok": False, "error": "approval_required", ...} so the planner can ask the user.
      - If `_approved` is present, it will be stripped before schema validation so
        `additionalProperties: false` schemas won't break.
    """
    try:
        tool_name = action.get("tool")
        args = action.get("args", {})
        if not isinstance(tool_name, str):
            return {"ok": False, "error": "invalid_action_format", "hint": "missing 'tool': str"}
        if tool_name not in tools:
            return {"ok": False, "error": "unknown_tool", "tool": tool_name}

        # --- Approval check (lazy import so agent runs even if policy file is absent) ---
        try:
            from .policies.approvals import requires_approval  # type: ignore
        except Exception:
            def requires_approval(_name: str) -> bool:  # type: ignore
                return False

        # Pop internal _approved BEFORE schema validation to avoid extra-prop errors
        internal_approved_flag = False
        if isinstance(args, dict) and "_approved" in args:
            try:
                internal_approved_flag = bool(args.get("_approved"))
            except Exception:
                internal_approved_flag = False
            # remove the internal field so schema validation doesn't fail
            args = {k: v for k, v in args.items() if k != "_approved"}

        if requires_approval(tool_name) and not internal_approved_flag:
            return {
                "ok": False,
                "error": "approval_required",
                "tool": tool_name,
                "hint": "This action requires explicit user approval. Re-issue with args including _approved=True after confirmation.",
            }

        # --- Schema validation ---
        spec = tools[tool_name]
        schema = spec.get("schema", {})
        err = _light_jsonschema_validate(args, schema)
        if err:
            return {"ok": False, "error": f"schema_error:{err}", "schema": schema}

        # --- Run tool ---
        runner = spec.get("runner")
        if not callable(runner):
            return {"ok": False, "error": "runner_missing", "tool": tool_name}

        obs = runner(args)
        if not isinstance(obs, dict):
            return {"ok": False, "error": "runner_return_invalid", "tool": tool_name}
        return obs

    except Exception as e:
        return {"ok": False, "error": f"execute_exception:{e}"}


def update_state(state: AgentState, thought: str, action: Dict[str, Any], observation: Dict[str, Any]) -> None:
    """Append a step and collect evidence where available."""
    state.steps.append(
        StepRecord(thought=thought, action=Action(action.get("tool"), action.get("args", {})), observation=observation)
    )

    # Evidence harvesting (URLs / DB citations)
    if observation.get("ok"):
        # Web pages
        if isinstance(observation.get("url"), str):
            state.evidence.append(observation["url"])
        # Links returned from web.get
        if isinstance(observation.get("links"), list):
            for l in observation["links"][:5]:
                if isinstance(l, dict) and isinstance(l.get("url"), str):
                    state.evidence.append(l["url"])
        # DB citations
        if isinstance(observation.get("sql"), str):
            state.evidence.append({"sql": observation["sql"]})

    if observation.get("finish"):
        state.finished = True
        state.final_answer = observation.get("answer")


def finished(state: AgentState) -> bool:
    return state.finished is True and isinstance(state.final_answer, str) and len(state.final_answer) > 0


def fallback_cot_sc(state: AgentState, planner_cot_sc: Optional[Callable[[AgentState], str]] = None) -> str:
    """
    CoT-SC majority vote fallback (hook). Provide your own implementation via planner_cot_sc.
    If not provided, we degrade gracefully by composing a best-effort answer from observations.
    """
    if callable(planner_cot_sc):
        try:
            return planner_cot_sc(state)
        except Exception:
            pass

    # Best-effort synthesis from recent observations
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


def synthesize_answer(state: AgentState) -> Dict[str, Any]:
    """Return final payload with answer, evidence, and full trajectory."""
    return {
        "ok": True,
        "answer": state.final_answer or "",
        "evidence": state.evidence,
        "trajectory": [
            {
                "thought": st.thought,
                "action": {"tool": st.action.tool, "args": st.action.args},
                "observation": st.observation,
            }
            for st in state.steps
        ],
        "steps_used": len(state.steps),
    }
    
def _log_trajectory_if_possible(
    mcp_client: Any,
    state: AgentState,
    start_ts_iso: Optional[str] = None,
) -> None:
    """
    Fire-and-forget logging via MCP tool 'log_agent_trajectory'. Never raise.
    """
    if mcp_client is None:
        return
    try:
        trajectory = [
            {
                "thought": st.thought,
                "action": {"tool": st.action.tool, "args": st.action.args},
                "observation": st.observation,
            }
            for st in state.steps
        ]
        args = {
            "user_goal": state.goal,
            "steps": trajectory,
            "final_answer": state.final_answer or "",
            "confidence": state.confidence,
            "start_ts": start_ts_iso,  # may be None -> DB uses NOW()
        }
        # Compat: if mcp_client exposes call_tool
        if hasattr(mcp_client, "call_tool"):
            mcp_client.call_tool("log_agent_trajectory", args)
        else:
            # Some clients expose the tool directly
            if hasattr(mcp_client, "log_agent_trajectory"):
                mcp_client.log_agent_trajectory(**args)  # type: ignore
    except Exception:
        # Never let telemetry crash the run
        pass



# --------------------
# Main entrypoint
# --------------------
def run(
    goal: str,
    make_prompt: Callable[..., str] = make_react_prompt,
    load_tools_fn: Callable[..., Dict[str, ToolSpec]] = load_all_tools,
    planner: Optional[Callable[[AgentState, Dict[str, ToolSpec], str], Tuple[str, Dict[str, Any]]]] = None,
    mcp_client: Any = None,
    gmail_client: Any = None,
    reflections: Optional[List[str]] = None,
    context: Optional[str] = None,
    intent_hint: Optional[str] = None,
    max_steps: int = 7,
    require_evidence_for_facts: bool = True,
    planner_cot_sc: Optional[Callable[[AgentState], str]] = None,
) -> Dict[str, Any]:
    """
    Run the ReAct loop to completion or fallback.
    - planner: REQUIRED to actually plan; if None, raises with a helpful message.
    """
    import time

    # --- sanity checks ---
    if load_tools_fn is None:
        raise RuntimeError("load_tools_fn not provided or import failed.")
    if make_prompt is None:
        raise RuntimeError("make_prompt not provided or import failed.")
    if planner is None:
        raise RuntimeError("planner callable is required (wire your LLM here).")

    # --- state init ---
    state = AgentState(
        goal=goal.strip(),
        reflections=reflections or [],
        context=context,
        intent_hint=intent_hint,
        max_steps=max_steps,
    )

    # timing
    t0 = time.time()
    try:
        # If you want an explicit ISO timestamp instead of DB NOW(), set it here.
        start_ts_iso = None
        # from datetime import datetime, timezone
        # start_ts_iso = datetime.now(timezone.utc).isoformat()
    except Exception:
        start_ts_iso = None

    # --- local helpers (kept here to avoid extra module deps) ---
    def _providers_kept_failing(st: AgentState) -> bool:
        """
        Returns True if free search providers (wikipedia/ddg) failed repeatedly
        in this run; used to waive the evidence gate in rare outage/ratelimit cases.
        """
        fails = 0
        for step in st.steps[-6:]:
            obs = step.observation or {}
            err = str(obs.get("error") or "")
            if (
                err.startswith("all_free_providers_failed")
                or err.startswith("duckduckgo_failed")
                or err.startswith("wikipedia_failed")
                or "Ratelimit" in err
            ):
                fails += 1
        return fails >= 2

    def _log_trajectory_if_possible(mcp, st: AgentState, *, start_ts_iso: Optional[str]) -> None:
        """
        Best-effort logging; never raises. Tries MCP 'log_react_run' tool or method if present.
        """
        try:
            payload = {
                "goal": st.goal,
                "intent_hint": st.intent_hint,
                "finished": bool(st.finished),
                "answer": st.final_answer,
                "steps_used": len(st.steps),
                "evidence": st.evidence,
                "start_ts": start_ts_iso,
                "duration_s": round(time.time() - t0, 3),
                "trajectory": [
                    {
                        "thought": s.thought,
                        "action": {"tool": s.action.tool, "args": s.action.args},
                        "observation": s.observation,
                    }
                    for s in st.steps
                ],
            }
            if mcp is None:
                return
            if hasattr(mcp, "call_tool"):
                try:
                    mcp.call_tool("log_react_run", payload)
                except Exception:
                    pass
            elif hasattr(mcp, "log_react_run"):
                try:
                    mcp.log_react_run(payload)
                except Exception:
                    pass
        except Exception:
            pass

    # --- load dynamic tools ---
    try:
        state.tools = load_tools_fn(mcp_client, gmail_client) or {}
    except Exception:
        state.tools = {}

    # --- main loop ---
    for _ in range(max_steps):
        # PLAN
        thought, action = plan_with_llm(state, planner)

        # loop detection
        recent_thoughts = [s.thought for s in state.steps] + [thought]
        if _looks_like_loop(recent_thoughts):
            observation = {
                "ok": False,
                "error": "loop_detected",
                "hint": "Reformulate query or try another tool/keywords.",
            }
            update_state(state, thought, action, observation)
            continue

        # ACT
        observation = execute_action(action, state.tools)

        # Evidence-before-finish (for factual queries) with narrow outage/ratelimit waiver
        if action.get("tool") == "Finish" and require_evidence_for_facts:
            looks_factual = (
                "?" in goal
                or any(w in goal.lower() for w in ["who", "what", "when", "where", "how", "cite", "source"])
            )
            # evidence already collected in previous steps
            has_urls = any(isinstance(e, str) and e.startswith(("http://", "https://")) for e in state.evidence)
            has_db = any(isinstance(e, dict) and "sql" in e for e in state.evidence)
            # evidence obtained in THIS step (before update_state)
            has_inline_url = isinstance(observation, dict) and "url" in observation

            if looks_factual and not (has_urls or has_db or has_inline_url):
                # waive only if free providers kept failing this run
                if not _providers_kept_failing(state):
                    observation = {
                        "ok": False,
                        "error": "evidence_required",
                        "hint": "Before finishing a factual answer, provide at least one grounded source (web.get) or DB query (db.select).",
                    }

        # UPDATE
        update_state(state, thought, action, observation)

        # DONE?
        if finished(state):
            _log_trajectory_if_possible(mcp_client, state, start_ts_iso=start_ts_iso)
            return synthesize_answer(state)

    # Step cap reached -> CoT-SC fallback
    final = fallback_cot_sc(state, planner_cot_sc=planner_cot_sc)
    state.final_answer = final
    state.finished = True
    _log_trajectory_if_possible(mcp_client, state, start_ts_iso=start_ts_iso)
    return synthesize_answer(state)
