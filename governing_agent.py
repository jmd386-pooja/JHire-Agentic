"""
Governing Conversational Agent
- LLM-only intent routing (no manual regex trees).
- DB questions: NL2SQL → MCP execute_database_query.
- Email actions delegated to EmailOrchestrator (constructor made signature-tolerant).
- Ranking delegated to EnhancedResumeRankingAgent (constructor tolerant).
- Email history from EmailAudit (MCP).
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterable

from langchain_google_genai import ChatGoogleGenerativeAI

# MCP stdio client
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Project modules
from email_agent import EmailOrchestrator
from nl2sql import NL2SQL
from mcp_client import EnhancedResumeRankingAgent
from mcp_client import MCPDB

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
        import os

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set")

        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.2,
            google_api_key=api_key,
            convert_system_message_to_human=True,
        )

        # Tools
        self.db = MCPDB(resume_server_script)
        self.ranker = self._init_ranker(model_name)
        self.mailer = self._init_mailer(resume_server_script)
        self.nl2sql = NL2SQL(model_name=model_name)

        # Session memory
        self.mem = Memory()

    # ---- tolerant constructors ------------------------------------------------
    def _init_mailer(self, path: str) -> EmailOrchestrator:
        return EmailOrchestrator(server_script_path=path)


    def _init_ranker(self, model_name: str) -> EnhancedResumeRankingAgent:
        try:
            return EnhancedResumeRankingAgent(model_name=model_name)
        except TypeError:
            # Some versions may not accept model_name
            return EnhancedResumeRankingAgent()

    async def _rank_and_persist(self, jd_text: str, top_n: int = 20) -> str:
        """
        Run the end-to-end server workflow (categorize → filter → initial score →
        final rank → store). Surface diagnostics to the user.
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
            diags = resp.get("diagnostics") or []
            extra = ("\n  • " + "\n  • ".join(str(x) for x in diags)) if diags else ""
            return f"Ranking failed: {reason}{extra}"

        # Extract counts/diagnostics
        counts = resp.get("counts") or {}
        job_id = resp.get("job_id")
        stored = resp.get("stored_in_db")
        finals = resp.get("final_rankings") or []

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


    # ------------- core routing -------------
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
            "Examples:\n"
            "Q: how many resumes are there?          -> db_query\n"
            "Q: count candidates in data science     -> db_query\n"
            "Q: list emails of Django folks          -> db_query\n"
            "Q: send invitations to the top 3        -> email_action\n"
            "Q: what messages did you send today     -> email_history\n"
            "Q: rank top 5 for this JD: ...          -> ranking\n\n"
            f"User: {text}\n"
            "Label:"
        )
        out = await self.llm.ainvoke(prompt)
        label = (out.content or "").strip().split()[0].lower()
        return label if label in {"email_history", "email_action", "ranking", "db_query", "general"} else "general"

    async def route_intent(self, text: str) -> str:
        try:
            return await self._llm_intent(text)
        except Exception:
            return "general"

    # ------------- util: result flatteners -------------
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

    def _extract_job_id_from_result(self, result: Any) -> Optional[int]:
        if isinstance(result, dict):
            for path in [
                ["job_id"],
                ["job", "id"],
                ["job", "job_id"],
                ["data", "id"],
                ["data", "job_id"],
                ["metadata", "id"],
                ["metadata", "job_id"],
                ["result", "id"],
                ["result", "job_id"],
            ]:
                cur = result
                for k in path:
                    if isinstance(cur, dict) and k in cur:
                        cur = cur[k]
                    else:
                        cur = None
                        break
                iv = self._as_int(cur)
                if iv is not None:
                    return iv
        for node in self._flatten(result):
            if isinstance(node, dict):
                if "job_id" in node and self._as_int(node.get("job_id")) is not None:
                    return self._as_int(node.get("job_id"))
                if node.get("type") == "job" and self._as_int(node.get("id")) is not None:
                    return self._as_int(node.get("id"))
        return None
    
    def _looks_like_job_description(self, text: str) -> bool:
        """
        Heuristic fallback so we don't misclassify long JD texts as db_query.
        Returns True if the text smells like a JD.
        """
        t = (text or "").lower()
        if not t:
            return False
        signals = [
            "requirements", "responsibilities", "we are looking for",
            "qualifications", "experience with", "skills", "role:",
            "position:", "about the role", "job description", "jd:",
        ]
        # long-ish text or lots of punctuation/newlines also strongly suggests JD
        return any(s in t for s in signals) or len(t) > 300 or t.count("-") > 3 or t.count("\n") > 2


    async def _rank_and_persist(self, jd_text: str, top_n: int = 20) -> str:
        """
        Run the end-to-end server workflow (categorize → filter → initial score →
        final rank → store). Surface diagnostics to the user and cache job_id/results.
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


    def _extract_ranked_from_result(self, result: Any, top_n: int) -> List[Dict[str, Any]]:
        name_keys = ["candidate_name", "name", "full_name"]
        email_keys = ["resume_email", "email", "candidate_email"]
        rank_keys = ["final_rank", "rank", "position", "index", "order"]
        score_keys = ["final_score", "match_score", "total_score", "overall_score", "score"]
        cands: List[Dict[str, Any]] = []

        for node in self._flatten(result):
            if not isinstance(node, dict):
                continue
            name_val = next(
                (node[k] for k in name_keys if k in node and isinstance(node[k], (str, int, float))),
                None,
            )
            if name_val is None:
                continue
            cand: Dict[str, Any] = {"candidate_name": str(name_val).strip()}
            email_val = next((node[k] for k in email_keys if k in node and isinstance(node[k], str)), None)
            cand["email"] = (email_val or "").strip() if isinstance(email_val, str) else ""
            rank_val = next((self._as_int(node[k]) for k in rank_keys if k in node), None)
            score_val = next((self._as_float(node[k]) for k in score_keys if k in node), None)
            cand["final_rank"], cand["match_score"] = rank_val, score_val
            cands.append(cand)

        if not cands:
            return []
        seen, unique = set(), []
        for c in cands:
            key = (c.get("candidate_name") or "", c.get("email") or "")
            if key in seen:
                continue
            seen.add(key)
            unique.append(c)

        if any(c.get("final_rank") is not None for c in unique):
            unique.sort(key=lambda x: (x.get("final_rank") is None, x.get("final_rank", 10**9)))
        elif any(x.get("match_score") is not None for x in unique):
            unique.sort(key=lambda x: (-float(x.get("match_score") or 0.0), str(x.get("candidate_name") or "")))
        else:
            unique.sort(key=lambda x: str(x.get("candidate_name") or ""))

        return unique[: top_n]

    # ------------- handlers -------------
    async def handle_general(self, text: str) -> str:
        system = "You are a helpful recruiting assistant. Be concise."
        resp = await self.llm.ainvoke(f"{system}\nUser: {text}")
        return resp.content or ""

    async def handle_ranking(self, text: str) -> str:
        m = re.search(r"(?:top|first)\s+(\d+)", text, re.IGNORECASE)
        top_n = int(m.group(1)) if m else (self.mem.last_top_n or 5)
        jd = text.strip()
        if not jd:
            return "Please provide a job description."

        msg = await self._rank_and_persist(jd, top_n)
        # Cache for follow-on email actions
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



    async def handle_email_history(self, text: str) -> str:
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



    # ------------- helper: try DB even if intent=general -------------
    async def _try_db_answer(self, text: str) -> Optional[str]:
        try:
            sql = await self.nl2sql.generate(text)
            r = await self.db.execute_database_query(sql)
            if r.get("status") != "success":
                return None
            rows = r.get("data", [])
            if rows is None:
                return None
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
        except Exception:
            return None

    # ------------- main entry -------------
    async def handle(self, text: str) -> str:
        intent = await self.route_intent(text)

        if intent == "email_history":
            return await self.handle_email_history(text)
        if intent == "email_action":
            return await self.handle_email(text)
        if intent == "ranking":
            return await self.handle_ranking(text)
        if intent == "db_query":
            # If this *looks* like a JD but LLM misclassified it, run ranking instead.
            if self._looks_like_job_description(text):
                return await self.handle_ranking(text)
            return await self.handle_db_query(text)

        # intent == general
        if self._looks_like_job_description(text):
            return await self.handle_ranking(text)

        maybe = await self._try_db_answer(text)
        if maybe is not None:
            return maybe
        return await self.handle_general(text)
