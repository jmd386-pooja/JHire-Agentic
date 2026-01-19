"""
Gmail MCP Client
-----------------
Connects to the Gmail AutoAuth MCP Server (@gongrzhe/server-gmail-autoauth-mcp)
and exposes convenience methods for sending emails and draft operations.

Env (optional):
- GMAIL_MCP_COMMAND  (default: "npx")
- GMAIL_MCP_ARGS     (default: "@gongrzhe/server-gmail-autoauth-mcp")
"""
from __future__ import annotations

import json
import logging
import asyncio
import os
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


class GmailMCPClient:
    def __init__(self) -> None:
        cmd = os.getenv("GMAIL_MCP_COMMAND", "npx")
        args_env = os.getenv("GMAIL_MCP_ARGS", "@gongrzhe/server-gmail-autoauth-mcp")
        if isinstance(args_env, str):
            self.args = args_env.split()
        else:
            self.args = ["@gongrzhe/server-gmail-autoauth-mcp"]
        self.server_params = StdioServerParameters(command=cmd, args=self.args)
        self.pool_size = int(os.getenv("GMAIL_MCP_POOL_SIZE", "4"))
        self._lock = asyncio.Lock()
        self._pool: List[ClientSession] = []
        self._pool_stdio: List[Any] = []
        self._rr = 0 
        
    async def connect(self) -> None:
        """Start (pool_size) Gmail MCP sessions and keep them alive."""
        async with self._lock:
            if self._pool:
                return  # already connected

            for _ in range(self.pool_size):
                cm = stdio_client(self.server_params)
                read, write = await cm.__aenter__()
                sess = ClientSession(read, write)
                await sess.__aenter__()
                await sess.initialize()

                self._pool.append(sess)
                self._pool_stdio.append(cm)

    async def aclose(self) -> None:
        """Close all persistent Gmail MCP sessions."""
        async with self._lock:
            # Close sessions
            for sess in self._pool:
                try:
                    await sess.__aexit__(None, None, None)
                except Exception:
                    pass

            # Close stdio managers (kills underlying processes)
            for cm in self._pool_stdio:
                try:
                    await cm.__aexit__(None, None, None)
                except Exception:
                    pass

            self._pool.clear()
            self._pool_stdio.clear()
            self._rr = 0



    async def _get_session(self) -> ClientSession:
        """Get a warm session (round-robin)."""
        await self.connect()
        async with self._lock:
            sess = self._pool[self._rr % len(self._pool)]
            self._rr += 1
            return sess


    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        *,
        html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "to": to,
            "subject": subject,
            "body": body,
        }
        if html:
            payload["mimeType"] = "multipart/alternative"
            payload["htmlBody"] = html
        else:
            payload["mimeType"] = "text/plain"
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        if attachments:
            payload["attachments"] = attachments

        try:
            sess = await self._get_session()
            result = await sess.call_tool("send_email", payload)
            if hasattr(result, "content") and result.content:
                item = result.content[0]
                text = getattr(item, "text", str(item))
                try:
                    return json.loads(text)
                except Exception:
                    return {"status": "ok", "result": text}
            return {"status": "ok", "result": str(result)}
        except Exception as e:
            logger.error("Gmail send_email failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def draft_email(
        self, to: List[str], subject: str, body: str, html: Optional[str] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "to": to,
            "subject": subject,
            "body": body,
            "mimeType": "text/plain" if not html else "multipart/alternative",
        }
        if html:
            payload["htmlBody"] = html
        try:
            sess = await self._get_session()
            result = await sess.call_tool("draft_email", payload)
            if hasattr(result, "content") and result.content:
                item = result.content[0]
                text = getattr(item, "text", str(item))
                try:
                    return json.loads(text)
                except Exception:
                    return {"status": "ok", "result": text}
            return {"status": "ok", "result": str(result)}
        except Exception as e:
            logger.error("Gmail draft_email failed: %s", e)
            return {"status": "error", "error": str(e)}
