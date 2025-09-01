"""
Governing Conversational Agent (stable routing + email history)
===============================================================
- Email commands take precedence (no re-ranking loops).
- Keeps last ranked list and last sent emails in memory.
- New 'email_history' intent answers: how many sent? who? what was sent?
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterable, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_client import EnhancedResumeRankingAgent
from email_agent import EmailOrchestrator
from nl2sql import NL2SQL


class MCPDB:
    def __init__(self, server_script_path: str = "mcp_server.py") -> None:
        self.server_params = StdioServerParameters(command="python", args=[server_script_path])

    async def tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as sess:
                await sess.initialize()
                res = await sess.call_tool(name, args)
                if hasattr(res, "content") and res.content:
                    item = res.content[0]
                    text = getattr(item, "text", str(item))
                    import json
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"status": "success", "result": text}
                return {"status": "success", "result": str(res)}

    async def sql(self, query: str) -> Dict[str, Any]:
        return await self.tool("execute_database_query", {"query": query})


@dataclass
class Memory:
    last_job_id: Optional[int] = None
    last_job_desc: Optional[str] = None
    last_top_n: Optional[int] = None
    last_ranked: List[Dict[str, Any]] = field(default_factory=list)
    last_sent: List[Dict[str, Any]] = field(default_factory=list)   # [{name,email,subject,type,result}]


# ---- intent helpers ----
def is_email_command(text: str) -> bool:
    t = text.lower()
    return (
        ("send" in t or "mail" in t or "email" in t)
        and any(k in t for k in ["congrats", "congratulation", "congratulations", "reject", "rejection", "offer"])
    )

def is_email_history_query(text: str) -> bool:
    t = text.lower()
    mentions_email = any(k in t for k in ["email", "emails", "mail"])
    asks_history = any(k in t for k in ["how many", "how much", "who", "whom", "which", "what have you sent", "what did you send", "list", "details", "sent"])
    return mentions_email and asks_history and not any(k in t for k in ["send ", "send\t", "send\n"])

def looks_like_job_description(text: str) -> bool:
    t = text.strip()
    tl = t.lower()
    if is_email_command(tl) or is_email_history_query(tl):
        return False
    long_enough = len(t) >= 120 or t.count("\n") >= 2 or t.count("- ") >= 2
    markers = ["we are looking for","we're looking for","we are seeking","we're seeking","responsibilities","requirements","qualifications","about the role","must have","nice to have","experience","engineer","developer","role","job description"]
    has_markers = any(m in tl for m in markers)
    is_question_like = any(q in tl for q in ["how many","count","list ","show ","who are","emails of","?"])
    return long_enough and has_markers and not is_question_like

def _is_jobdesc_count_intent(text: str) -> bool:
    t = text.lower()
    if not any(k in t for k in ["how many","count","number of","no. of","no of","how  job","how job"]):
        return False
    has_job = "job" in t or "jobs" in t
    desc_markers = ["description","descriptions","desc","jd","posting","postings","opening","openings","req","requisition","decription","decriptions"]
    has_descriptor = any(m in t for m in desc_markers)
    return has_job and has_descriptor


class GoverningAgent:
    def __init__(self, model_name: str = "gemini-2.0-flash-thinking-exp", resume_server_script: str = "mcp_server.py") -> None:
        import os
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.2, google_api_key=api_key, convert_system_message_to_human=True)
        self.db = MCPDB(resume_server_script)
        self.ranker = EnhancedResumeRankingAgent(model_name=model_name)
        self.mailer = EmailOrchestrator(resume_server_script=resume_server_script)
        self.nl2sql = NL2SQL(model_name=model_name)
        self.mem = Memory()

    # -------- intent routing --------
    def _rule_intent(self, text: str) -> str:
        t = text.lower().strip()
        if is_email_history_query(t): return "email_history"
        if is_email_command(t): return "email_action"
        if looks_like_job_description(text): return "ranking"
        if any(k in t for k in ["rank","process job","job description","top candidates"]): return "ranking"
        if any(k in t for k in ["how many","count","list","show","who are","emails of","emails "," filter"," in "," from "," with "," without "]):
            if any(x in t for x in ["developer","engineer","candidate","resume","people","folks","job description","job descriptions","jobs"]):
                return "db_query"
        return "general"

    async def _llm_intent(self, text: str) -> str:
        prompt = ("Classify as one of: email_history, email_action, ranking, db_query, general. "
                  "If it asks how many/what/who emails were sent, return email_history. "
                  "If it asks to send congrats/rejection/offer emails, return email_action. "
                  "Raw job descriptions → ranking.\nUser: " + text)
        out = await self.llm.ainvoke(prompt)
        label = (out.content or "").strip().split()[0].lower()
        return label if label in {"email_history","email_action","ranking","db_query","general"} else "general"

    async def route_intent(self, text: str) -> str:
        if is_email_history_query(text): return "email_history"
        if is_email_command(text): return "email_action"
        if looks_like_job_description(text): return "ranking"
        label = self._rule_intent(text)
        if label == "general":
            try: label = await self._llm_intent(text)
            except Exception: pass
        return label
    
    async def _resumes_columns(self) -> set:
        # Use PRAGMA now that the MCP server allows it
        r = await self.db.sql("PRAGMA table_info(resumes)")
        cols = set()
        if r.get("status") == "success":
            for row in r.get("data", []):
                name = row.get("name")
                if name:
                    cols.add(name.lower())
        # Hard fallback to known fields if PRAGMA failed
        if not cols:
            cols = {"category", "role_category", "job_category", "current_role",
                    "technical_skills", "work_experience"}
        return cols

    def _normalize_role_phrase(self, phrase: str) -> tuple[list[str], str]:
        """
        'data science developers' -> (['data','science'], 'data science')
        Handles hyphens, plurals, synonyms.
        """
        t = phrase.lower().strip().replace("-", " ")
        repl = {
            "fullstack": "full stack",
            "full stack developers": "full stack",
            "full stack developer": "full stack",
            "data scientists": "data science",
            "data scientist": "data science",
            "ml engineer": "machine learning",
            "ml engineers": "machine learning",
            "ml developers": "machine learning",
            "frontend": "front end",
            "backend": "back end",
        }
        for k, v in repl.items():
            t = t.replace(k, v)

        stop = {"developer","developers","engineer","engineers","people","folks","candidates","profiles",
                "role","roles","job","jobs","the","a","an","of","for","with","and","to","in","at"}
        toks = [w for w in t.split() if w and w not in stop]
        toks = [w for w in toks if len(w) >= 2]

        # keep order, unique
        seen, out = set(), []
        for w in toks:
            if w not in seen:
                seen.add(w); out.append(w)
        phrase_norm = " ".join(out)
        return out, phrase_norm

    async def _count_resumes_by_tokens(self, tokens: list[str], phrase_norm: str) -> int:
        cols = await self._resumes_columns()

        preferred = ["category","role_category","job_category","current_role","technical_skills","work_experience"]
        use = [c for c in preferred if c in cols]
        if not use:
            use = ["category"]  # safest fallback

        # corpus across chosen columns
        parts = [f"LOWER(COALESCE({c},''))" for c in use]
        corpus = " || ' ' || ".join(parts)

        # AND every token
        and_conds = []
        for tok in tokens:
            esc = tok.replace("'", "''")
            and_conds.append(f"({corpus} LIKE '%{esc}%')")
        and_sql = " AND ".join(and_conds) if and_conds else ""

        # OR exact phrase across each column
        phrase_sql = ""
        phrase_norm = (phrase_norm or "").strip()
        if phrase_norm:
            ph = phrase_norm.replace("'", "''")
            or_conds = [f"(LOWER(COALESCE({c},'')) LIKE '%{ph}%')" for c in use]
            phrase_sql = " OR ".join(or_conds)

        # combine WHERE
        if and_sql and phrase_sql:
            where = f"( {and_sql} ) OR ( {phrase_sql} )"
        elif and_sql:
            where = and_sql
        elif phrase_sql:
            where = phrase_sql
        else:
            # if we ever get here, tokens/phrase were empty – answer 0, not “all”
            return 0

        q = f"SELECT COUNT(*) AS cnt FROM resumes WHERE {where}"
        r = await self.db.sql(q)
        if r.get("status") == "success":
            return int(r.get("data", [{}])[0].get("cnt", 0))
        return 0




    # -------- result flatteners --------
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
            if value is None or isinstance(value, bool): return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        try:
            if value is None or isinstance(value, bool): return None
            return float(value)
        except Exception:
            return None

    def _extract_job_id_from_result(self, result: Any) -> Optional[int]:
        if isinstance(result, dict):
            for path in [["job_id"],["job","id"],["job","job_id"],["data","id"],["data","job_id"],["metadata","id"],["metadata","job_id"],["result","id"],["result","job_id"]]:
                cur = result
                for k in path:
                    if isinstance(cur, dict) and k in cur: cur = cur[k]
                    else: cur = None; break
                iv = self._as_int(cur)
                if iv is not None: return iv
        for node in self._flatten(result):
            if isinstance(node, dict):
                if "job_id" in node and self._as_int(node.get("job_id")) is not None: return self._as_int(node.get("job_id"))
                if node.get("type") == "job" and self._as_int(node.get("id")) is not None: return self._as_int(node.get("id"))
        return None

    def _extract_ranked_from_result(self, result: Any, top_n: int) -> List[Dict[str, Any]]:
        name_keys, email_keys = ["candidate_name","name","full_name"], ["resume_email","email"]
        rank_keys, score_keys = ["final_rank","rank","position","index","order"], ["match_score","total_score","overall_score","score"]
        cands: List[Dict[str, Any]] = []
        for node in self._flatten(result):
            if not isinstance(node, dict): continue
            name_val = next((node[k] for k in name_keys if k in node and isinstance(node[k], (str,int,float))), None)
            if name_val is None: continue
            cand: Dict[str, Any] = {"candidate_name": str(name_val).strip()}
            email_val = next((node[k] for k in email_keys if k in node and isinstance(node[k], str)), None)
            cand["email"] = (email_val or "").strip() if isinstance(email_val, str) else ""
            rank_val = next((self._as_int(node[k]) for k in rank_keys if k in node), None)
            score_val = next((self._as_float(node[k]) for k in score_keys if k in node), None)
            cand["final_rank"], cand["match_score"] = rank_val, score_val
            cands.append(cand)
        if not cands: return []
        seen, unique = set(), []
        for c in cands:
            key = (c.get("candidate_name") or "", c.get("email") or "")
            if key in seen: continue
            seen.add(key); unique.append(c)
        if any(c.get("final_rank") is not None for c in unique):
            unique.sort(key=lambda x: (x.get("final_rank") is None, x.get("final_rank", 10**9)))
        elif any(x.get("match_score") is not None for x in unique):
            unique.sort(key=lambda x: (-float(x.get("match_score") or 0.0), str(x.get("candidate_name") or "")))
        else:
            unique.sort(key=lambda x: str(x.get("candidate_name") or ""))
        return unique[: top_n]

    # -------- handlers --------
    async def handle_general(self, text: str) -> str:
        system = "You are a helpful recruiting assistant. Be concise."
        resp = await self.llm.ainvoke(f"{system}\nUser: {text}")
        return resp.content or ""

    async def handle_ranking(self, text: str) -> str:
        m = re.search(r"(?:top|first)\s+(\d+)", text, re.IGNORECASE)
        top_n = int(m.group(1)) if m else (self.mem.last_top_n or 5)
        jd = text.strip() if looks_like_job_description(text) else (re.search(r":\s*(.+)$", text.strip(), re.DOTALL).group(1).strip() if re.search(r":\s*(.+)$", text.strip(), re.DOTALL) else self.mem.last_job_desc)
        if not jd: return "Please provide a job description (e.g., “rank top 5: Junior Python developer, remote …”)."

        result = await self.ranker.process_job_with_workflow_tracking(jd, top_n)
        top = self._extract_ranked_from_result(result, top_n)
        job_id = self._extract_job_id_from_result(result)

        self.mem.last_job_desc, self.mem.last_top_n, self.mem.last_ranked = jd, top_n, top
        if isinstance(job_id, int): self.mem.last_job_id = job_id

        if top:
            lines = []
            for r in top:
                rank = r.get("final_rank"); name = r.get("candidate_name") or "Unknown"
                score = r.get("match_score"); email = r.get("email") or ""
                line = f"{rank if rank is not None else '-'}.\u0020{name}"
                if score is not None: line += f" (score {score:.3f})"
                if email: line += f" – {email}"
                lines.append(line)
            return "Ranking complete.\nTop candidates:\n" + "\n".join(lines)
        return "Ranking completed for the provided job description, but I couldn't fetch the ranked list."

    async def handle_db_query(self, text: str) -> str:
        t = text.lower().strip()

        # quick jobdescription count (typo tolerant)
        if _is_jobdesc_count_intent(t):
            r = await self.db.sql("SELECT COUNT(*) AS cnt FROM jobdescription")
            if r.get("status") != "success":
                return f"DB error: {r.get('error') or r}"
            cnt = r.get("data", [{}])[0].get("cnt", 0)
            return f"There are {cnt} job descriptions in the database."

        # how many X are there …?
        m = re.search(r"(?:how many|count)\s+(.+?)\s+(?:do we have|are there|present|available|in db|in database)\s*$", t)
        if m and "email" not in t:
            phrase = m.group(1).strip()
            tokens, phrase_norm = self._normalize_role_phrase(phrase)
            cnt = await self._count_resumes_by_tokens(tokens, phrase_norm)

            # If zero, auto-diagnose DB path to catch mismatch early
            if cnt == 0:
                info = await self.db.tool("db_info", {})
                hint = ""
                try:
                    di = info.get("data") or {}
                    seen = ", ".join(di.get("distinct_category", [])[:10])
                    hint = f" (db: {di.get('db_path','?')}; categories seen: {seen or 'none'})"
                except Exception:
                    pass
            else:
                hint = ""

            label = phrase_norm or phrase
            if label.endswith(" developer") or label.endswith(" developers"):
                label = label.rsplit(" ", 1)[0]
            return f"We currently have {cnt} {label} candidates in the database.{hint}"

        # NL→SQL fallback
        try:
            sql = await self.nl2sql.generate(text)
            r = await self.db.sql(sql)
            if r.get("status") != "success":
                return f"DB error: {r.get('error') or r}"
            data = r.get("data", [])
            if not data:
                return "No matching records found."
            keys = list(data[0].keys())
            sample = data[: min(5, len(data))]
            head = " | ".join(keys)
            rows = [" | ".join(str(row.get(k, "")) for k in keys) for row in sample]
            out = head + "\n" + "\n".join(rows)
            if len(data) > len(sample):
                out += f"\n... (+{len(data)-len(sample)} more)"
            return out
        except Exception as e:
            return f"Couldn't formulate a safe SQL for that question: {e}"

    async def handle_email(self, text: str) -> str:
        tl = text.lower()
        explicit: Optional[Dict[str, str]] = None
        if any(k in tl for k in ["ranked now","ranked","these candidates","those candidates","them"]):
            if self.mem.last_ranked:
                rec: Dict[str, str] = {}
                missing: List[str] = []
                for r in self.mem.last_ranked:
                    name = (r.get("candidate_name") or "").strip()
                    email = (r.get("email") or "").strip()
                    if not name: continue
                    if email: rec[name] = email
                    else: missing.append(name)
                if missing:
                    escaped = [n.lower().replace("'", "''") for n in missing]
                    if escaped:
                        in_list = ",".join(f"'{v}'" for v in escaped)
                        q = f"SELECT full_name, email FROM resumes WHERE email IS NOT NULL AND LOWER(full_name) IN ({in_list})"
                        r = await self.db.sql(q)
                        if r.get("status") == "success":
                            for row in r.get("data", []):
                                if row.get("full_name") and row.get("email"):
                                    rec[row["full_name"]] = row["email"]
                explicit = rec or None

        result = await self.mailer.act_on_instruction(text, job_id_override=self.mem.last_job_id, explicit_recipients=explicit)
        if result.get("status") != "success": return f"Email action failed: {result.get('error')}"
        self.mem.last_sent = result.get("details", [])
        return f"Email action completed. Messages sent: {result.get('sent', 0)}."

    async def handle_email_history(self, text: str) -> str:
        # Prefer this-session memory
        if self.mem.last_sent:
            total = len(self.mem.last_sent)
            lines = []
            for it in self.mem.last_sent:
                name = it.get("name") or "Unknown"
                email = it.get("email") or ""
                subj = it.get("subject") or ""
                typ  = it.get("type") or ""
                lines.append(f"- {name} — {email} — {typ} — “{subj}”")
            return f"I sent {total} email(s) just now:\n" + "\n".join(lines)

        # Otherwise, read from audit table
        r = await self.db.sql("SELECT COUNT(*) AS cnt FROM email_audit")
        total = (r.get("data", [{}])[0].get("cnt", 0) if r.get("status") == "success" else 0)
        r2 = await self.db.sql("""
            SELECT sent_at, candidate_name, candidate_email, email_type, subject, username, password, exam_link, send_status
            FROM email_audit
            ORDER BY id DESC
            LIMIT 20
        """)
        if r2.get("status") != "success":
            return f"Email history error: {r2.get('error') or r2}"

        rows = r2.get("data", [])
        if not rows:
            return f"No email history found. (Total logged: {total})"

        lines = []
        for row in rows:
            when = row.get("sent_at") or ""
            name = row.get("candidate_name") or ""
            email = row.get("candidate_email") or ""
            typ  = row.get("email_type") or ""
            subj = row.get("subject") or ""
            user = row.get("username") or ""
            pwd  = row.get("password") or ""
            link = row.get("exam_link") or ""
            ok   = row.get("send_status") or ""
            parts = [f"{when} — {name} — {email} — {typ} — “{subj}”"]
            if user: parts.append(f"username:{user}")
            if pwd:  parts.append(f"password:{pwd}")
            if link: parts.append(f"link:{link}")
            parts.append(f"status:{ok}")
            lines.append(" | ".join(parts))

        return f"Total emails logged: {total}\nMost recent:\n" + "\n".join(lines)

    async def handle(self, text: str) -> str:
        intent = await self.route_intent(text)
        if intent == "email_history": return await self.handle_email_history(text)
        if intent == "email_action":  return await self.handle_email(text)
        if intent == "ranking":       return await self.handle_ranking(text)
        if intent == "db_query":      return await self.handle_db_query(text)
        return await self.handle_general(text)
