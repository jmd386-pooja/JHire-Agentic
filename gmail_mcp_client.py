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

    @asynccontextmanager
    async def session(self):
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as sess:
                await sess.initialize()
                yield sess

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
            async with self.session() as sess:
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
            async with self.session() as sess:
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
