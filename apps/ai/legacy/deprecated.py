"""
Deprecation helpers for quarantined symbols.

Import these as temporary shims to avoid import errors while we migrate callers.
Each function raises a clear error with guidance.
"""

class DeprecatedError(RuntimeError):
    pass

def _msg(name: str) -> str:
    return (
        f"'{name}' has been deprecated and quarantined.\n"
        f"Use the ReAct pathway via `governing_agent.GoverningAgent.handle(...)` instead.\n"
        f"If you must resurrect this flow, move it out of `legacy/` and expose its capabilities as discrete tools."
    )

def categorizer_agent(*_a, **_k):
    raise DeprecatedError(_msg("categorizer_agent"))

def old_resume_flow(*_a, **_k):
    raise DeprecatedError(_msg("old_resume_flow"))

def pipeline_entrypoint(*_a, **_k):
    raise DeprecatedError(_msg("pipeline_entrypoint"))
