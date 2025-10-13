# ai/governing_agent.py
"""
Governing Conversational Agent (Hybrid)
- Primary paths preserved:
    • DB questions: NL2SQL → MCP execute_database_query
    • Email actions: EmailOrchestrator
    • Ranking: EnhancedResumeRankingAgent + server `process_complete_job`
    • Email history: "EmailAudit" via MCP
- Dynamic fallback:
    • ReAct loop with Gemini planner for anything else or mixed/novel tasks
- Safety:
    • Tolerant constructors
    • Single, de-duplicated _rank_and_persist
"""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterable, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI

# Project modules (kept)
from email_agent import EmailOrchestrator
from nl2sql import NL2SQL
from mcp_client import EnhancedResumeRankingAgent
from mcp_client import MCPDB

# ReAct fallback
from react_agent import run as react_run
from mcp_safe_adapter import SafeMCPAdapter
from mcp_client import MCPClient as OriginalMCPClient
from gmail_mcp_client import GmailMCPClient

from policies.cot_sc import make_gemini_cot_sc
from policies.reflexion import ReflexionStore, default_key_from_goal, should_write_lesson, make_lesson



try:
    import google.generativeai as genai  # pip install google-generativeai
except Exception:
    genai = None


# ----------------------------
# Ephemeral session memory
# ----------------------------
@dataclass
class Memory:
    last_job_id: Optional[int] = None
    last_job_desc: Optional[str] = None
    last_top_n: Optional[int] = None
    last_ranked: List[Dict[str, Any]] = field(default_factory=list)
    last_sent: List[Dict[str, Any]] = field(default_factory=list)   # [{name,email,subject,type,result}]


# ----------------------------
# Governing Agent
# ----------------------------
class GoverningAgent:
    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-thinking-exp",
        resume_server_script: str = "mcp_server.py",
    ) -> None:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY / GEMINI_API_KEY not set")

        # LLM used for intent hinting (fast/cheap)
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.2,
            google_api_key=api_key,
            convert_system_message_to_human=True,
        )

        # Tools (kept)
        self.db = MCPDB(resume_server_script)
        self.ranker = self._init_ranker(model_name)
        self.mailer = self._init_mailer(resume_server_script)
        self.nl2sql = NL2SQL(model_name=model_name)

        # Session memory
        self.mem = Memory()
        self.reflex = ReflexionStore(path=os.getenv("REFLEXION_PATH", "data/reflexion_store.jsonl"), max_per_key=5)


    # ---- tolerant constructors ------------------------------------------------
    def _init_mailer(self, path: str) -> EmailOrchestrator:
        # Make the constructor tolerant to signature diffs
        try:
            return EmailOrchestrator(server_script_path=path)
        except TypeError:
            return EmailOrchestrator(path)  # older signature

    def _init_ranker(self, model_name: str) -> EnhancedResumeRankingAgent:
        try:
            return EnhancedResumeRankingAgent(model_name=model_name)
        except TypeError:
            return EnhancedResumeRankingAgent()

    # ----------------------------
    # Utilities
    # ----------------------------
    @staticmethod
    def _flatten(obj: Any) -> Iterable[Any]:
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from GoverningAgent._flatten(v)
        elif isinstance(obj, (list, tuple)):
            for it in obj:
                yield from GoverningAgent._flatten(it)

    @staticmethod
    def _as_int(value: Any) -> Optional[int]:
        try:
            if value is None or isinstance(value, bool):
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            if value is None or isinstance(value, bool):
                return None
            return float(value)
        except Exception:
            return None

    def _looks_like_job_description(self, text: str) -> bool:
        """
        Heuristic fallback so we don't misclassify long JD texts as db_query.
        """
        t = (text or "").lower()
        if not t:
            return False
        signals = [
            "requirements", "responsibilities", "we are looking for",
            "qualifications", "experience with", "skills", "role:",
            "position:", "about the role", "job description", "jd:",
        ]
        return any(s in t for s in signals) or len(t) > 300 or t.count("-") > 3 or t.count("\n") > 2

    # ----------------------------
    # Ranking (kept, de-duplicated)
    # ----------------------------
    async def _rank_and_persist(self, jd_text: str, top_n: int = 20) -> str:
        """
        End-to-end server workflow (categorize → filter → initial score →
        final rank → store). Shows brief diagnostics and caches results.
        """
        try:
            resp = await self.db.call_tool(
                "process_complete_job",
                {"job_description": jd_text, "top_n": int(top_n)}
            )
        except Exception as e:
            return f"Ranking failed: MCP error: {e}"

        # Hard error from server
        if not isinstance(resp, dict) or resp.get("status") != "success":
            reason = (resp or {}).get("error") or "unknown error"
            diags = (resp or {}).get("diagnostics") or []
            extra = ("\n  • " + "\n  • ".join(str(x) for x in diags)) if diags else ""
            return f"Ranking failed: {reason}{extra}"

        # Extract counts/diagnostics
        counts = resp.get("counts") or {}
        job_id = resp.get("job_id")
        stored = resp.get("stored_in_db")
        finals = resp.get("final_rankings") or []

        # Cache for follow-on email actions
        try:
            if job_id is not None:
                self.mem.last_job_id = job_id
            self.mem.last_job_desc = jd_text
            self.mem.last_top_n = int(top_n)
            self.mem.last_ranked = list(finals) if isinstance(finals, list) else []
        except Exception:
            pass

        # Pretty preview
        lines = []
        for r in finals[: min(5, len(finals))]:
            name = r.get("candidate_name") or "Unknown"
            rank = r.get("final_rank") or "-"
            score = r.get("final_score")
            lines.append(f"{rank}. {name}" + (f" (score {float(score):.3f})" if score is not None else ""))

        # Counts / DB status
        diag = []
        if counts:
            diag.append(
                "Resumes(total={resumes_total}, filtered={filtered_candidates}, "
                "initial_scored={initial_scored}, final_ranked={final_ranked})".format(**{
                    "resumes_total": counts.get("resumes_total"),
                    "filtered_candidates": counts.get("filtered_candidates"),
                    "initial_scored": counts.get("initial_scored"),
                    "final_ranked": counts.get("final_ranked"),
                })
            )
        if stored is not None:
            diag.append(f"DB store: {'ok' if stored else 'failed'} (job_id={job_id})")

        lines_block = ("\n  • " + "\n  • ".join(lines)) if lines else ""
        diag_block = ("\n  • " + "\n  • ".join(diag)) if diag else ""

        if finals:
            return f"Ranking saved: job_id={job_id}, rows={len(finals)}{lines_block}{diag_block}"

        # No finals — explain why
        reason = resp.get("error") or resp.get("warning") or "No candidates made it to the final ranking stage."
        more = resp.get("diagnostics") or []
        more_block = ("\n  • " + "\n  • ".join(str(x) for x in more)) if more else ""
        return f"Ranking completed but no results.\nReason: {reason}{diag_block}{more_block}"

    # ----------------------------
    # Intent routing (kept)
    # ----------------------------
    async def _llm_intent(self, text: str) -> str:
        """
        Pure-LLM intent classification.
        Returns exactly one of: email_history, email_action, ranking, db_query, general
        """
        prompt = (
            "You are routing a user's request for a recruiting assistant.\n"
            "Return ONLY one label from {email_history, email_action, ranking, db_query, general}.\n\n"
            "Guidance:\n"
            "- db_query: asks to count, list, show, filter, or query data "
            "(e.g., 'how many resumes are there', 'count candidates', 'list emails of X', "
            "'show job descriptions', 'which candidates in category Y').\n"
            "- email_action: asks to send/draft emails (offers, invitations, congratulations, rejections, follow-ups).\n"
            "- email_history: asks what emails were sent or details of sent emails.\n"
            "- ranking: provides a job description and asks to evaluate/rank candidates.\n"
            "- general: small talk or anything else.\n\n"
            f"User: {text}\n"
            "Label:"
        )
        out = await self.llm.ainvoke(prompt)
        label = (out.content or "").strip().split()[0].lower()

        # Heuristic: long JD-ish text should be "ranking"
        if label == "db_query" and self._looks_like_job_description(text):
            return "ranking"
        return label if label in {"email_history", "email_action", "ranking", "db_query", "general"} else "general"

    async def route_intent(self, text: str) -> str:
        try:
            return await self._llm_intent(text)
        except Exception:
            return "general"

    # ----------------------------
    # Handlers (kept)
    # ----------------------------
    async def handle_ranking(self, text: str) -> str:
        m = re.search(r"(?:top|first)\s+(\d+)", text, re.IGNORECASE)
        top_n = int(m.group(1)) if m else (self.mem.last_top_n or 5)
        jd = text.strip()
        if not jd:
            return "Please provide a job description."
        msg = await self._rank_and_persist(jd, top_n)
        self.mem.last_job_desc = jd
        self.mem.last_top_n = top_n
        return msg

    async def handle_db_query(self, text: str) -> str:
        try:
            sql = await self.nl2sql.generate(text)
        except Exception as e:
            return f"I couldn't generate a safe SQL for that question: {e}"

        r = await self.db.execute_database_query(sql)
        if r.get("status") != "success":
            return f"Database error: {r.get('error') or r}"

        rows = r.get("data", [])
        if not rows:
            return "No matching records found."

        first = rows[0]
        if len(first) == 1:
            k = next(iter(first))
            v = first[k]
            try:
                num = int(v) if isinstance(v, (int, float, str)) else v
                return f"{num}"
            except Exception:
                pass

        cols = list(first.keys())
        sample = rows[: min(5, len(rows))]
        head = " | ".join(cols)
        body = "\n".join(" | ".join(str(r.get(c, "")) for c in cols) for r in sample)
        suffix = f"\n... (+{len(rows)-len(sample)} more)" if len(rows) > len(sample) else ""
        return head + "\n" + body + suffix

    async def handle_email(self, text: str) -> str:
        result = await self.mailer.act_on_instruction(
            text,
            job_id_override=self.mem.last_job_id,
            explicit_recipients=None,
        )
        if result.get("status") not in {"success", "partial"}:
            return f"Email action failed: {result.get('error') or result}"

        # cache for 'how many' questions
        self.mem.last_sent = result.get("details", [])
        sent = int(result.get("sent") or 0)
        attempted = int(result.get("attempted") or 0)
        failures = result.get("failures") or []

        if not attempted:
            return "No recipients were selected for emailing."

        if failures:
            # show top 3 failures inline
            head = failures[:3]
            lines = [f"- {f.get('name','?')} <{f.get('email','')}> — {f.get('reason','unknown')}" for f in head]
            more = f" (+{len(failures)-len(head)} more)" if len(failures) > len(head) else ""
            return f"Email action {result.get('status')}. Sent: {sent}/{attempted}. Some failed:\n" + "\n".join(lines) + more

        return f"Email action success. Sent: {sent}/{attempted}."

    async def handle_email_history(self, _text: str) -> str:
        # If we just sent emails in this session, show that first
        if self.mem.last_sent:
            total = len(self.mem.last_sent)
            lines = []
            for it in self.mem.last_sent:
                name = it.get("name") or "Unknown"
                email = it.get("email") or ""
                subj = it.get("subject") or ""
                typ = it.get("type") or ""
                lines.append(f"- {name} — {email} — {typ} — “{subj}”")
            return f"I sent {total} email(s) just now:\n" + "\n".join(lines)

        # Count totals from the canonical table name
        r = await self.db.execute_database_query(
            'SELECT COUNT(*)::int AS total, COUNT(*) FILTER (WHERE send_status ILIKE \'ok\')::int AS ok FROM public."EmailAudit"'
        )
        total = (r.get("data", [{}])[0].get("total", 0) if r.get("status") == "success" else 0)
        ok = (r.get("data", [{}])[0].get("ok", 0) if r.get("status") == "success" else 0)

        # Recent entries (no sensitive fields)
        r2 = await self.db.execute_database_query(
            """
            SELECT sent_at, candidate_name, candidate_email, email_type, subject,
                   exam_link, send_status
            FROM public."EmailAudit"
            ORDER BY sent_at DESC, id DESC
            LIMIT 20
            """
        )
        if r2.get("status") != "success":
            return f"Email history error: {r2.get('error') or r2}"

        rows = r2.get("data", [])
        if not rows:
            return f"No email history found. (Total logged: {total}, ok={ok})"

        lines = []
        for row in rows:
            when = row.get("sent_at") or ""
            name = row.get("candidate_name") or ""
            email = row.get("candidate_email") or ""
            typ = row.get("email_type") or ""
            subj = row.get("subject") or ""
            link = row.get("exam_link") or ""
            status = row.get("send_status") or ""
            parts = [f"{when} — {name} — {email} — {typ} — “{subj}”"]
            if link:
                parts.append(f"link:{link}")
            parts.append(f"status:{status}")
            lines.append(" | ".join(parts))

        header = f"Email history (last 20). Total={total}, ok={ok}"
        return header + "\n" + "\n".join(lines)

    # ----------------------------
    # Gemini planner + ReAct fallback
    # ----------------------------
    @staticmethod
    def _parse_thought_and_action(text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extract FIRST 'Thought:' and FIRST 'Action: {...}' JSON object from the model output.
        Returns (thought, action_dict). Raises ValueError if no valid Action JSON found.
        """
        thought_match = re.search(r"Thought:\s*(.*)", text)
        thought = thought_match.group(1).strip() if thought_match else ""

        action_match = re.search(r'Action:\s*({.*})', text, flags=re.DOTALL)
        if not action_match:
            raise ValueError("Planner did not emit an Action JSON on the Action: line.")
        action_raw = action_match.group(1).strip()

        # Balance braces (trim trailing junk after balanced JSON)
        counter, end_idx = 0, None
        for i, ch in enumerate(action_raw):
            if ch == "{":
                counter += 1
            elif ch == "}":
                counter -= 1
                if counter == 0:
                    end_idx = i + 1
                    break
        if end_idx is not None:
            action_raw = action_raw[:end_idx]

        action = json.loads(action_raw)
        if not isinstance(action, dict) or "tool" not in action or "args" not in action:
            raise ValueError("Action JSON missing 'tool' or 'args'.")
        if not isinstance(action["args"], dict):
            raise ValueError("Action.args must be an object.")
        return thought, action

    @staticmethod
    def _gemini_planner(state, tools, prompt) -> Tuple[str, Dict[str, Any]]:
        """
        Calls Gemini with the compiled ReAct prompt and returns (thought, action_dict).
        Env:
          - GOOGLE_API_KEY or GEMINI_API_KEY
          - GEMINI_REACT_MODEL (optional; default "gemini-1.5-flash")
        """
        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not google_key:
            raise RuntimeError("Missing GOOGLE_API_KEY / GEMINI_API_KEY for Gemini planner.")
        if genai is None:
            raise RuntimeError("google-generativeai not installed. pip install google-generativeai")
        genai.configure(api_key=google_key)

        model_name = os.getenv("GEMINI_REACT_MODEL", "gemini-2.0-flash-thinking-exp")
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(prompt)

        # Robust extraction of text
        text = getattr(resp, "text", None)
        if not text and getattr(resp, "candidates", None):
            parts = []
            for cand in resp.candidates:
                for p in getattr(cand, "content", {}).parts or []:
                    if getattr(p, "text", None):
                        parts.append(p.text)
            text = "\n".join(parts).strip() if parts else ""

        if not text:
            # fail safe—force a Finish so your API doesn't crash
            return (
                "No usable response from Gemini; finishing with a placeholder.",
                {"tool": "Finish", "args": {"answer": "Gemini returned no text.", "evidence": []}},
            )

        return GoverningAgent._parse_thought_and_action(text)

    # ----------------------------
    # Unified entrypoint
    # ----------------------------
    async def handle(self, user_text: str, *, react_override: bool = False) -> Dict[str, Any]:
        """
        Hybrid handler:
          - If react_override=True -> always use ReAct (Gemini planner).
          - Else route by intent:
              db_query      -> NL2SQL + execute_database_query
              ranking       -> _rank_and_persist
              email_action  -> EmailOrchestrator
              email_history -> EmailAudit summary
              general/other -> ReAct fallback
        """
        if react_override:
            return await self._run_react(user_text)

        intent = await self.route_intent(user_text)
        if intent == "db_query":
            return {"ok": True, "answer": await self.handle_db_query(user_text)}
        if intent == "ranking":
            return {"ok": True, "answer": await self.handle_ranking(user_text)}
        if intent == "email_action":
            return {"ok": True, "answer": await self.handle_email(user_text)}
        if intent == "email_history":
            return {"ok": True, "answer": await self.handle_email_history(user_text)}

        # Fallback: dynamic ReAct flow
        return await self._run_react(user_text)

    async def _run_react(self, user_text: str) -> Dict[str, Any]:
        """
        Run the ReAct loop with Gemini planner and safe MCP adapter.
        """
        # Build EXISTING clients (use the same params your app uses)
        original_mcp = OriginalMCPClient()  # pass args if your client requires them
        gmail_client = GmailMCPClient()     # pass args if required

        # Wrap only for the ReAct layer (non-invasive)
        safe_mcp = SafeMCPAdapter(original_mcp)

        reflections = []
        # your existing guard, if present:
        # reflections.extend(self.irreversible_action_guard(user_text, intent_hint))
        # Reflexion lessons for this goal bucket:
        key = default_key_from_goal(user_text)
        reflections.extend(self.reflex.get_lessons(key, limit=3))

        try:
            result = react_run(
                goal=user_text,
                planner=GoverningAgent._gemini_planner,
                mcp_client=safe_mcp,
                gmail_client=gmail_client,
                max_steps=7,
                require_evidence_for_facts=True,
                reflections=reflections,
                planner_cot_sc=make_gemini_cot_sc(n=5, temperature=0.7),
            )
        except Exception as e:
            # fail safe—return a structured result
            result = {
                "ok": False,
                "answer": "Planner or runtime error.",
                "error": str(e),
                "evidence": [],
                "trajectory": [],
                "steps_used": 0,
            }
            
        try:
            write, tags = should_write_lesson(result, max_steps=7)
            if write:
                lesson = make_lesson(user_text, result)
                self.reflex.add_lesson(default_key_from_goal(user_text), user_text, lesson, tags=tags)
        except Exception:
            # Reflexion should never crash the run
            pass

        return result
