from typing import Any, Dict

class SafeMCPAdapter:
    """
    Wrap your EXISTING MCP client. Normalizes responses to {ok, data|error}.
    """

    def __init__(self, underlying_client: Any):
        self._c = underlying_client

    def call(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if hasattr(self._c, "call_tool"):
                raw = self._c.call_tool(tool, args or {})
            else:
                if tool == "execute_database_query" and hasattr(self._c, "execute_database_query"):
                    raw = self._c.execute_database_query(args.get("sql", ""))
                elif tool == "get_database_stats" and hasattr(self._c, "get_database_stats"):
                    raw = self._c.get_database_stats()
                elif hasattr(self._c, tool):
                    # optional: call same-named method as a last resort
                    raw = getattr(self._c, tool)(**(args or {}))
                else:
                    return {"ok": False, "error": f"unsupported_tool:{tool}"}

            if isinstance(raw, dict) and "ok" in raw:
                return raw
            return {"ok": True, "data": raw}
        except Exception as e:
            return {"ok": False, "error": f"call_exception:{e}", "tool": tool}

    # Convenience used by tools
    def execute_database_query(self, sql: str) -> Dict[str, Any]:
        return self.call("execute_database_query", {"sql": sql})

    def get_database_stats(self) -> Dict[str, Any]:
        return self.call("get_database_stats", {})
