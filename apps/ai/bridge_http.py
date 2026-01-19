# apps/ai/bridge_http.py
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Union

from fastapi import FastAPI
from gmail_mcp_client import GmailMCPClient
from mcp_client import MCPClient
from pydantic import BaseModel

from governing_agent import GoverningAgent


app = FastAPI(title="JHire Agent Bridge")

# Singleton agent + lock so we only build it once
_agent: Optional[GoverningAgent] = None
_agent_lock = asyncio.Lock()

mcp = MCPClient(persistent=True)

gmail_client = GmailMCPClient()

    
@app.on_event("startup")
async def startup():
    await mcp.connect()
    await gmail_client.connect()

@app.on_event("shutdown")
async def shutdown():
    await mcp.aclose()
    await gmail_client.aclose()

class ChatReq(BaseModel):
    message: str

class ChatResp(BaseModel):
    status: str
    reply: Union[str, Dict[str, Any]]
    diagnostics: Optional[Dict[str, Any]] = None

async def _get_agent() -> GoverningAgent:
    global _agent
    if _agent is not None:
        return _agent
    async with _agent_lock:
        if _agent is None:
            _agent = GoverningAgent()
        return _agent

@app.post("/chat", response_model=ChatResp)
async def chat(req: ChatReq) -> Dict[str, Any]:
    """
    Equivalent to running run_conversational_agent.py and typing the prompt:
    calls GoverningAgent.handle(req.message) and returns the reply.
    """
    agent = await _get_agent()
    try:
        result = await agent.handle(req.message)
        # Your agent sometimes returns plain strings. If it returns a dict, passthrough.
        if isinstance(result, (str, int, float)):
            return {"status": "success", "reply": str(result)}
        return {"status": "success", "reply": result}
    except Exception as e:
        return {
            "status": "error",
            "reply": f"Agent failed: {e}",
            "diagnostics": {"type": type(e).__name__},
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
