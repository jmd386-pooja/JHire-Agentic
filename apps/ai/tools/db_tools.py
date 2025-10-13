# ai/tools/db_tools.py
from __future__ import annotations
from typing import Dict, Any, Optional, List, Tuple, Union
import re
import asyncio

from nl2sql import NL2SQL

ALLOWED_SELECT = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

# ---------- tiny async bridges ----------

def _ensure_event_loop():
    """Get or create an event loop that we can use in a sync context (Windows-safe)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop
    except Exception:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def _is_awaitable(x: Any) -> bool:
    return asyncio.iscoroutine(x) or isinstance(x, asyncio.Future) or hasattr(x, "__await__")

def _await_maybe(x: Any) -> Any:
    """Run a coroutine/future to completion from sync code; otherwise return the value."""
    if _is_awaitable(x):
        loop = _ensure_event_loop()
        return loop.run_until_complete(x)
    return x

# ---------- helpers ----------

def _normalize_sql(nl2sql_result: Union[str, Tuple, Dict[str, Any]]) -> str:
    """
    Accepts various possible outputs and extracts an SQL string.
      - str: the SQL
      - (sql, params): take first item as SQL
      - {'sql': '...', ...}: use 'sql' key
    """
    if isinstance(nl2sql_result, str):
        return nl2sql_result
    if isinstance(nl2sql_result, (tuple, list)) and nl2sql_result:
        return str(nl2sql_result[0])
    if isinstance(nl2sql_result, dict) and "sql" in nl2sql_result:
        return str(nl2sql_result["sql"])
    return str(nl2sql_result)

def _looks_like_select(sql_or_q: str) -> bool:
    return isinstance(sql_or_q, str) and ALLOWED_SELECT.match(sql_or_q.strip()) is not None

def _deep_unwrap(resp: Any) -> Any:
    """
    Recursively unwrap common adapter shapes until we reach the actual tool result.
    - Awaits awaitables at any depth.
    - Unwraps {'ok': True, 'data': ...} repeatedly.
    """
    # resolve awaitables
    resp = _await_maybe(resp)

    # unwrap nested {'ok': True, 'data': ...} / {'success': True, 'data': ...}
    seen = 0
    while isinstance(resp, dict) and "data" in resp and seen < 6:
        inner = resp["data"]
        inner = _await_maybe(inner)
        # if inner looks like the real tool payload, stop
        if isinstance(inner, dict) and ("status" in inner or "data" in inner or "columns" in inner):
            resp = inner
        else:
            # sometimes adapters wrap scalars; promote them
            resp = inner
        seen += 1

    # final await if still awaitable
    resp = _await_maybe(resp)
    return resp

# ---------- main tool spec ----------

def make_db_select_spec(mcp_client: Any) -> Dict[str, Any]:
    """
    ToolSpec for 'db.select':
      - NL question -> await NL2SQL.generate(...) -> SQL (SELECT-only)
      - Executes via MCP 'execute_database_query' (deep unwraps adapter returns)
      - Returns preview rows + columns and places the SQL in observation for evidence harvesting
    """

    def _runner(args: Dict[str, Any]) -> Dict[str, Any]:
        question = (args or {}).get("question") or ""
        limit = int((args or {}).get("limit") or 50)

        if not isinstance(question, str) or not question.strip():
            return {"ok": False, "error": "missing_question", "hint": "Provide args.question (string)."}

        # 1) NL -> SQL (await if async). If user passed a literal SELECT, prefer that.
        try:
            if _looks_like_select(question):
                sql = question.strip()
            else:
                gen = NL2SQL()
                sql_raw = _await_maybe(gen.generate(question))  # generate is async in your project
                sql = _normalize_sql(sql_raw).strip()
        except Exception as e:
            return {"ok": False, "error": f"nl2sql_error:{e}"}

        # 2) Safety: enforce SELECT-only
        if not _looks_like_select(sql):
            return {"ok": False, "error": "non_select_sql_rejected", "sql": str(sql)[:200]}

        # 3) LIMIT guard if caller/LLM didn't add it and it's not a COUNT
        low = sql.lower()
        if " limit " not in low and not low.startswith("select count("):
            sql = f"SELECT * FROM ({sql}) AS t LIMIT {limit}"

        # 4) Execute via MCP server
        if mcp_client is None:
            return {"ok": False, "error": "mcp_client_missing", "sql": sql}

        try:
            if hasattr(mcp_client, "call_tool"):
                raw = mcp_client.call_tool("execute_database_query", {"query": sql})
            elif hasattr(mcp_client, "execute_database_query"):
                raw = mcp_client.execute_database_query(sql)
            else:
                return {"ok": False, "error": "mcp_call_unavailable", "sql": sql}
            resp = _deep_unwrap(raw)
        except Exception as e:
            return {"ok": False, "error": f"db_exec_error:{e}", "sql": sql}

        # 5) Normalize final tool payload (expecting your DB tool shape)
        if not isinstance(resp, dict):
            return {"ok": False, "error": "db_exec_invalid_response", "sql": sql}

        # Some servers still wrap once more
        if "status" not in resp and "data" in resp and isinstance(resp["data"], dict):
            resp = resp["data"]

        if resp.get("status") != "success":
            return {"ok": False, "error": str(resp.get("error") or resp), "sql": sql}

        rows: List[Dict[str, Any]] = resp.get("data", []) or []
        cols: List[str] = resp.get("columns") or (list(rows[0].keys()) if rows else [])
        
        if not rows and isinstance(resp.get("data"), (int, float)):
            rows = [{"count": int(resp["data"])}]
            cols = ["count"]

        # If the server accidentally returned a scalar count, normalize to a row
        if not rows and cols and len(cols) == 1 and "results_count" in resp:
            # unlikely, but keep a guard
            rows = [{cols[0]: resp.get("results_count")}]

        preview = rows[: min(len(rows), 10)]

        return {
            "ok": True,
            "sql": sql,                  # harvested into evidence
            "rows": preview,             # sample
            "rows_total": int(resp.get("results_count") or len(rows)),
            "columns": cols,
        }

    return {
        "description": "Answer DB questions by translating NL → safe SELECT and executing it.",
        "schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["question"],
            "additionalProperties": False,
        },
        "runner": _runner,
    }
