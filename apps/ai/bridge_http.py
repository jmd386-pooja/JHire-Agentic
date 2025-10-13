# bridge_http.py
from __future__ import annotations
from typing import Any, Dict, Optional, List

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ReAct + planner + clients
from react_agent import run as react_run
from mcp_safe_adapter import SafeMCPAdapter
from gmail_mcp_client import GmailMCPClient
from governing_agent import GoverningAgent

# IMPORTANT: use the fixed MCPClient that accepts server_script_path and cwd
# (Make sure your mcp_client.py __init__ has server_script_path/cwd/env args as we discussed.)
from mcp_client import MCPClient as OriginalMCPClient


# ------------------------------------------------------------------------------
# Configuration (read once at import time)
# ------------------------------------------------------------------------------
APP_TITLE = "ReAct Agent Gateway"
APP_VERSION = "1.1"

# Allow overriding location of your MCP server & working dir via env
# Defaults are safe if mcp_server.py is in the same folder as this file.
MCP_SERVER_SCRIPT = os.getenv("MCP_SERVER_SCRIPT", os.path.abspath("mcp_server.py"))
MCP_SERVER_CWD    = os.getenv("MCP_SERVER_CWD",    os.getcwd())

# Fail fast if the script isn’t where we think it is
if not os.path.isfile(MCP_SERVER_SCRIPT):
    raise RuntimeError(
        f"MCP_SERVER_SCRIPT not found: {MCP_SERVER_SCRIPT}\n"
        "Set env MCP_SERVER_SCRIPT to the absolute path of your mcp_server.py"
    )

# Gemini key check (the planner will also check, but we can surface it early)
if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
    # Don’t crash the server, but warn loudly in logs; requests will error with a 500 if planner is used.
    print("[WARN] GOOGLE_API_KEY / GEMINI_API_KEY not set. Gemini planner will fail.")


# ------------------------------------------------------------------------------
# App & I/O schemas
# ------------------------------------------------------------------------------
app = FastAPI(title=APP_TITLE, version=APP_VERSION)

class ChatIn(BaseModel):
    text: str
    reflections: Optional[List[str]] = None
    intent_hint: Optional[str] = None
    max_steps: Optional[int] = 7
    require_evidence_for_facts: Optional[bool] = True

class ChatOut(BaseModel):
    ok: bool
    answer: str
    evidence: list
    steps_used: int
    trajectory: list
    error: Optional[str] = None


# ------------------------------------------------------------------------------
# Singletons (created once on startup, reused per-request)
# ------------------------------------------------------------------------------
_mcp_client: Optional[OriginalMCPClient] = None
_safe_mcp: Optional[SafeMCPAdapter] = None
_gmail_client: Optional[GmailMCPClient] = None


@app.on_event("startup")
def _startup() -> None:
    """
    Start the MCP stdio server **once** and wrap with the safety adapter.
    This avoids spawning multiple processes (and avoids WinError 267 from bad CWD).
    """
    global _mcp_client, _safe_mcp, _gmail_client

    # Start MCP client with explicit script path and CWD (critical on Windows)
    try:
        _mcp_client = OriginalMCPClient(
            server_script_path=MCP_SERVER_SCRIPT,
            cwd=MCP_SERVER_CWD,
            env=os.environ.copy(),
        )
    except Exception as e:
        # If we can’t start, we still bring the API up but fail requests with 503
        _mcp_client = None
        print(f"[ERROR] Failed to start MCP server: {e}")

    _safe_mcp = SafeMCPAdapter(_mcp_client) if _mcp_client else None

    # Your Gmail client (if you don’t use it yet, it’s fine to leave blank ctor)
    try:
        _gmail_client = GmailMCPClient()
    except Exception as e:
        _gmail_client = None
        print(f"[WARN] Gmail client failed to init: {e}")


@app.on_event("shutdown")
def _shutdown() -> None:
    """Cleanly stop the MCP server if your client exposes a close/terminate."""
    try:
        if _mcp_client and hasattr(_mcp_client, "close"):
            _mcp_client.close()
    except Exception:
        pass


# ------------------------------------------------------------------------------
# Health
# ------------------------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, str]:
    # Also report whether the MCP process is running
    mcp_status = "up" if (_mcp_client and getattr(_mcp_client, "is_running", lambda: True)()) else "down"
    return {"status": "ok", "mcp": mcp_status}


# ------------------------------------------------------------------------------
# Chat
# ------------------------------------------------------------------------------
@app.post("/chat", response_model=ChatOut)
def chat(inp: ChatIn) -> Dict[str, Any]:
    # Defensive checks
    if _safe_mcp is None:
        raise HTTPException(
            status_code=503,
            detail=f"MCP server not available. Check path & CWD.\n"
                   f"Script: {MCP_SERVER_SCRIPT}\nCWD: {MCP_SERVER_CWD}"
        )

    # Planner: reuse the Gemini-only planner from GoverningAgent
    planner = GoverningAgent._gemini_planner

    # Call the ReAct loop
    try:
        result = react_run(
            goal=inp.text,
            planner=planner,
            mcp_client=_safe_mcp,
            gmail_client=_gmail_client,
            reflections=inp.reflections or [],
            intent_hint=inp.intent_hint,
            max_steps=int(inp.max_steps or 7),
            require_evidence_for_facts=bool(inp.require_evidence_for_facts),
        )
    except Exception as e:
        # Bubble a structured error to the client
        raise HTTPException(status_code=500, detail=f"react_run failed: {e}")

    # Normalize the response
    return {
        "ok": bool(result.get("ok", True)),
        "answer": str(result.get("answer", "")),
        "evidence": result.get("evidence", []),
        "trajectory": result.get("trajectory", []),
        "steps_used": int(result.get("steps_used", 0)),
        "error": result.get("error"),
    }
