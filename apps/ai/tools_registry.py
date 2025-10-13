from __future__ import annotations

"""
Dynamic Tool Registry
---------------------
Imports concrete runners for web.search and web.get from tools.web_search / tools.web_get.
"""

from typing import Any, Callable, Dict, TypedDict, Optional, List
import json
import re
from tools.web_tools import spec_web_search, spec_web_get
from tools.db_tools import make_db_select_spec

class ToolSpec(TypedDict):
    name: str
    description: str
    schema: Dict[str, Any]
    runner: Callable[[Dict[str, Any]], Dict[str, Any]]


# --------------------------
# Utility: safe JSON schema
# --------------------------
def _schema_object(required: List[str], props: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": props,
    }


# --------------------------
# DB tool runner (NL2SQL)
# --------------------------
_SELECT_RE = re.compile(r"^\s*select\s", re.IGNORECASE | re.DOTALL)

def _is_safe_select(sql: str) -> bool:
    if not _SELECT_RE.search(sql or ""):
        return False
    bad = [" insert ", " update ", " delete ", " drop ", " alter ", " create ", " grant ", " revoke ", ";"]
    lo = f" {sql.lower()} "
    return not any(tok in lo for tok in bad)

# --------------------------
# Email runners (Gmail MCP)
# --------------------------
def _run_email_draft(args: Dict[str, Any], gmail_client: Any) -> Dict[str, Any]:
    try:
        to = args.get("to") or []
        subject = args.get("subject") or ""
        body = args.get("body") or ""
        if not isinstance(to, list) or not subject or not body:
            return {"ok": False, "error": "invalid_args", "hint": "Requires to:list, subject:str, body:str"}

        if hasattr(gmail_client, "draft_email"):
            res = gmail_client.draft_email(to=to, subject=subject, body=body)
        else:
            return {"ok": False, "error": "gmail_client_missing_draft"}
        return {"ok": True, **(res if isinstance(res, dict) else {"result": res})}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _run_email_send(args: Dict[str, Any], gmail_client: Any) -> Dict[str, Any]:
    try:
        draft_id = args.get("draft_id")
        if not draft_id:
            return {"ok": False, "error": "invalid_args", "hint": "Requires draft_id:str"}

        if hasattr(gmail_client, "send_email"):
            res = gmail_client.send_email(draft_id=draft_id)
        else:
            return {"ok": False, "error": "gmail_client_missing_send"}
        return {"ok": True, **(res if isinstance(res, dict) else {"result": res})}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --------------------------
# Rank pipeline (MCP server)
# --------------------------
def _run_rank_full_process(args: Dict[str, Any], mcp_client: Any) -> Dict[str, Any]:
    try:
        jd_text = args.get("jd_text") or ""
        top_k = int(args.get("top_k") or 10)
        if not jd_text:
            return {"ok": False, "error": "invalid_args", "hint": "Requires jd_text:str"}

        if hasattr(mcp_client, "call_tool"):
            res = mcp_client.call_tool("process_complete_job", {"jd_text": jd_text, "top_k": top_k})
        else:
            return {"ok": False, "error": "mcp_client_missing_call_tool"}
        return {"ok": True, **(res if isinstance(res, dict) else {"result": res})}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --------------------------
# Finish tool
# --------------------------
def _run_finish(args: Dict[str, Any]) -> Dict[str, Any]:
    answer = args.get("answer")
    evidence = args.get("evidence", [])
    if not answer or not isinstance(answer, str):
        return {"ok": False, "error": "invalid_args", "hint": "Requires answer:str"}
    return {"ok": True, "finish": True, "answer": answer, "evidence": evidence}


# --------------------------
# Registry builder
# --------------------------
def load_all_tools(mcp_client: Any, gmail_client: Any) -> Dict[str, ToolSpec]:
    """
    Build the tool map. Concrete web runners are imported from tools.*.
    """
    tools: Dict[str, ToolSpec] = {}

    # Web tools
    tools["web.search"] = spec_web_search()
    tools["web.get"]    = spec_web_get()

    # Database (safe NL2SQL SELECT)
    tools["db.select"] = make_db_select_spec(mcp_client)

    # Email (via Gmail MCP)
    tools["email.draft"] = ToolSpec(
        name="email.draft",
        description="Draft an email. This does NOT send; sending should require approval.",
        schema=_schema_object(
            required=["to", "subject", "body"],
            props={
                "to": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string", "minLength": 1},
                "body": {"type": "string", "minLength": 1},
            },
        ),
        runner=lambda args: _run_email_draft(args, gmail_client),
    )
    tools["email.send"] = ToolSpec(
        name="email.send",
        description="Send an existing draft email. Use only after explicit approval.",
        schema=_schema_object(
            required=["draft_id"],
            props={"draft_id": {"type": "string", "minLength": 1}},
        ),
        runner=lambda args: _run_email_send(args, gmail_client),
    )

    # Ranking pipeline
    tools["rank.full_process"] = ToolSpec(
        name="rank.full_process",
        description="Analyze a job description and produce ranked candidates with reasoning.",
        schema=_schema_object(
            required=["jd_text"],
            props={"jd_text": {"type": "string", "minLength": 10}, "top_k": {"type": "integer", "minimum": 1, "maximum": 200}},
        ),
        runner=lambda args: _run_rank_full_process(args, mcp_client),
    )

    # Finish
    tools["Finish"] = ToolSpec(
        name="Finish",
        description="Conclude with final answer and optional evidence citations.",
        schema=_schema_object(
            required=["answer"],
            props={"answer": {"type": "string"}, "evidence": {"type": "array"}},
        ),
        runner=_run_finish,
    )

    return tools
