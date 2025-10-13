from __future__ import annotations
"""
Approval policy for potentially irreversible / high-risk tools.

How it works
------------
- `requires_approval(tool_name)` returns True if the tool should only run after
  explicit user confirmation.
- Read-only tools are allow-listed (never require approval).
- Known risky tools are block-listed (always require approval).
- A fallback regex flags verbs like send/write/delete/update/deploy/publish/post.
- You can extend the policy at runtime with `ALLOWLIST.update({...})` or
  `BLOCKLIST.update({...})` before the ReAct loop starts.

Usage in the agent (already wired):
    from ai.policies.approvals import requires_approval
    if requires_approval(tool) and not approved:
        # return {"ok": False, "error": "approval_required", ...}
"""

from typing import Set
import os
import re

# --- Core allow/block lists ---------------------------------------------------

# Tools that are read-only by design: safe to run without asking.
ALLOWLIST: Set[str] = {
    "web.search",
    "web.get",
    "db.select",
    "rank.full_process",   # analysis-only (no side effects)
    "Finish",
}

# Tools that are side-effectful or commonly irreversible: always ask first.
BLOCKLIST: Set[str] = {
    "email.send",
    "filesystem.write",
    "filesystem.delete",
    "storage.put",
    "storage.delete",
    "db.upsert",
    "db.write",
    "deploy.start",
    "deploy.run",
    "deploy.apply",
}

# Fallback heuristic: verbs that typically imply a write or public action.
_RISKY_VERB = re.compile(r"(send|write|delete|update|deploy|publish|post|commit|push|approve)\b", re.IGNORECASE)

# --- Optional: allow overrides via environment variables ----------------------
# You can inject comma-separated overrides at runtime, e.g.:
#   APPROVAL_ALLOWLIST="custom.read,metrics.get"
#   APPROVAL_BLOCKLIST="reports.publish,calendar.send_invites"
def _env_set(name: str) -> Set[str]:
    raw = os.getenv(name, "")
    return {x.strip() for x in raw.split(",") if x.strip()}

ALLOWLIST.update(_env_set("APPROVAL_ALLOWLIST"))
BLOCKLIST.update(_env_set("APPROVAL_BLOCKLIST"))

# --- Public API ---------------------------------------------------------------

def requires_approval(tool_name: str) -> bool:
    """
    Returns True if this tool should require explicit user approval before running.
    """
    if not isinstance(tool_name, str) or not tool_name:
        return False

    # Explicit allow/block first
    if tool_name in ALLOWLIST:
        return False
    if tool_name in BLOCKLIST:
        return True

    # Heuristic: risky verbs in the name imply an action worth confirming
    if _RISKY_VERB.search(tool_name):
        return True

    # Default: no approval required
    return False


def reason(tool_name: str) -> str:
    """
    Optional helper to explain WHY approval is required (for UX/tooltips/logs).
    """
    if tool_name in BLOCKLIST:
        return "This tool performs an irreversible or high-risk action."
    if _RISKY_VERB.search(tool_name or ""):
        return "The tool name suggests a write or public action."
    if tool_name in ALLOWLIST:
        return "This tool is read-only."
    return "No approval required by default."
