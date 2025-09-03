"""
Governing Conversational Agent (stable routing + email history)
===============================================================
- Email commands take precedence (no re-ranking loops).
- Keeps last ranked list and last sent emails in memory.
- Email flow uses MCP execute_database_query (no direct DB driver).
- Invitation emails pull credentials from public.resumes view:
  candidate_exam_url, candidate_temp_password, candidate_temp_name,
  candidate_exam_date, candidate_expiry.
"""

from __future__ import annotations

import re, asyncio, json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterable, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_client import EnhancedResumeRankingAgent
from email_agent import EmailOrchestrator
from nl2sql import NL2SQL

class PlanKeys:
    INTENTS = {"email_history","email_action","ranking","db_query","general"}
    ACTIONS = {"invite","congratulations","rejection","offer","unknown"}

# ---------------- MCP DB thin wrapper ----------------
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
                    try:
                        return json.loads(text)
                    except Exception:
                        return {"status": "success", "result": text}
                return {"status": "success", "result": str(res)}

    async def sql(self, query: str) -> Dict[str, Any]:
        return await self.tool("execute_database_query", {"query": query})


# ---------------- ephemeral memory ----------------
@dataclass
class Memory:
    last_job_id: Optional[int] = None
    last_job_desc: Optional[str] = None
    last_top_n: Optional[int] = None
    last_ranked: List[Dict[str, Any]] = field(default_factory=list)
    last_sent: List[Dict[str, Any]] = field(default_factory=list)   # [{name,email,subject,type,result}]


# ---------------- intent helpers ----------------
def is_email_command(text: str) -> bool:
    t = text.lower()
    return (
        ("send" in t or "mail" in t or "email" in t)
        and any(k in t for k in ["congrats", "congratulation", "congratulations", "reject", "rejection", "offer", "invite", "invitation"])
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


# ---------------- governing agent ----------------
class GoverningAgent:
    def __init__(self, model_name: str = "gemini-2.0-flash-thinking-exp", resume_server_script: str = "mcp_server.py") -> None:
        import os
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.2, google_api_key=api_key, convert_system_message_to_human=True)
        self.db = MCPDB(resume_server_script)
        self.ranker = EnhancedResumeRankingAgent(model_name=model_name)
        # IMPORTANT: our orchestrator expects `server_script` (uses MCP execute_database_query internally)
        self.mailer = EmailOrchestrator(server_script=resume_server_script)
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
    
    async def _plan_with_llm(self, text: str) -> Dict[str, Any]:
        """
        Ask the LLM to return a strict JSON plan describing:
          - intent: one of email_history | email_action | ranking | db_query | general
          - action_kind (if email_action): invite|congratulations|rejection|offer|unknown
          - recipient_spec (if email_action): { "send_all": bool, "top_n": int|null, "names": [str] }
          - job_description (if ranking or explicit JD present)
          - job_id (if user referenced a job to act on)
          - sql_question (if db_query)
        Defaults:
          - If the user says “send the emails” with no specifics → action_kind = "invite"
          - If both top_n and names are present, names win.
        """
        sys_prompt = (
            "You are an orchestration planner for a recruiting assistant. "
            "Return ONLY valid JSON. Do not include any other text."
        )
        user_prompt = f"""
            Create a JSON plan for this user message.

            Rules:
            - intent ∈ ["email_history","email_action","ranking","db_query","general"]
            - If the user asks about previously sent mails (#, who, what), intent="email_history".
            - If the user wants to send any kind of mail, intent="email_action".
            - If the message is a standalone job description, intent="ranking".
            - If it's a data question answered by SQL, intent="db_query".
            - Otherwise "general".

            - For email_action:
              - action_kind ∈ ["invite","congratulations","rejection","offer","unknown"].
              - If the user doesn't specify type but says "send the emails", assume "invite".
              - Build recipient_spec:
                  {{
                    "send_all": boolean,            # true if "everyone"/"all"
                    "top_n": integer|null,          # e.g. "top 5"
                    "names": [string]               # e.g. ["Jane Doe","John Smith"]
                  }}
                If multiple are present, prefer names > top_n > send_all.

            - Extract job_id if the user mentions it (number-like tokens).
            - Extract job_description if they paste one.

            - If a SQL-like counting/listing question, intent="db_query" and fill sql_question with a paraphrase.

            Return JSON with keys:
            {{
              "intent": "...",
              "action_kind": "...",
              "recipient_spec": {{"send_all": false, "top_n": null, "names": []}},
              "job_id": null,
              "job_description": "",
              "sql_question": ""
            }}

            User message:
            {text}
            JSON:
        """
        out = await self.llm.ainvoke(sys_prompt + "\n" + user_prompt)
        raw = (out.content or "").strip()
    
        # Extract JSON safely
        import json, re
        def _just_json(s: str) -> str:
            m = re.search(r"\{.*\}\s*$", s, re.S)
            return m.group(0) if m else s
        try:
            plan = json.loads(_just_json(raw))
        except Exception:
            # last resort: return a minimal plan
            plan = {"intent":"general","action_kind":"unknown",
                    "recipient_spec":{"send_all":False,"top_n":None,"names":[]},
                    "job_id":None,"job_description":"","sql_question":""}
    
        # normalize
        intent = str(plan.get("intent","general")).lower()
        action_kind = str(plan.get("action_kind","unknown")).lower()
        if intent not in PlanKeys.INTENTS: intent = "general"
        if action_kind not in PlanKeys.ACTIONS: action_kind = "unknown"
        rs = plan.get("recipient_spec") or {}
        send_all = bool(rs.get("send_all", False))
        top_n = rs.get("top_n", None)
        try:
            top_n = int(top_n) if top_n is not None else None
        except Exception:
            top_n = None
        names = [str(x).strip() for x in (rs.get("names") or []) if str(x).strip()]
    
        return {
            "intent": intent,
            "action_kind": action_kind,
            "recipient_spec": {"send_all": send_all, "top_n": top_n, "names": names},
            "job_id": plan.get("job_id"),
            "job_description": plan.get("job_description") or "",
            "sql_question": plan.get("sql_question") or "",
        }

    async def route_intent(self, text: str) -> str:
        # Let the LLM decide first
        try:
            plan = await self._plan_with_llm(text)
            if plan["intent"] in PlanKeys.INTENTS:
                # Cache bits we might reuse
                if plan.get("job_description"):
                    self.mem.last_job_desc = plan["job_description"]
                self._last_plan = plan  # store for handlers
                return plan["intent"]
        except Exception:
            pass

        # Fallback original rules (rarely hit)
        return self._rule_intent(text)

    # -------- DB helpers --------
    async def _resumes_columns(self) -> set:
        r = await self.db.sql(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='resumes'"
        )
        cols = set()
        if r.get("status") == "success":
            for row in r.get("data", []):
                n = row.get("name")
                if n:
                    cols.add(n.lower())
        return cols

    async def _latest_job_id_via_mcp(self) -> Optional[int]:
        r = await self.db.sql(
            "SELECT id FROM public.jobdescription ORDER BY created_at DESC LIMIT 1"
        )
        if r and r.get("status") == "success" and r.get("data"):
            return int(r["data"][0]["id"])
        return None

    # -------- role phrase → tokens --------
    def _normalize_role_phrase(self, phrase: str) -> tuple[list[str], str]:
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

        seen, out = set(), []
        for w in toks:
            if w not in seen:
                seen.add(w); out.append(w)
        phrase_norm = " ".join(out)
        return out, phrase_norm

    async def _count_resumes_by_tokens(self, tokens: list[str], phrase_norm: str) -> int:
        cols = await self._resumes_columns()
        preferred = ["category","role_category","job_category","current_role","technical_skills","work_experience"]
        use = [c for c in preferred if c in cols] or ["category"]

        parts = [f"LOWER(COALESCE({c},''))" for c in use]
        corpus = " || ' ' || ".join(parts)

        and_conds = []
        for tok in tokens:
            esc = tok.replace("'", "''")
            and_conds.append(f"({corpus} LIKE '%{esc}%')")
        and_sql = " AND ".join(and_conds) if and_conds else ""

        phrase_sql = ""
        phrase_norm = (phrase_norm or "").strip()
        if phrase_norm:
            ph = phrase_norm.replace("'", "''")
            or_conds = [f"(LOWER(COALESCE({c},'')) LIKE '%{ph}%')" for c in use]
            phrase_sql = " OR ".join(or_conds)

        if and_sql and phrase_sql:
            where = f"( {and_sql} ) OR ( {phrase_sql} )"
        elif and_sql:
            where = and_sql
        elif phrase_sql:
            where = phrase_sql
        else:
            return 0

        q = f"SELECT COUNT(*) AS cnt FROM public.resumes WHERE {where}"
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

    # ---------------- Handlers ----------------
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

    async def _db_sql_with_llm(self, text: str) -> str:
        """
        Ask the LLM to produce ONE safe SELECT SQL for Postgres that answers the user's question.
        Must reference only whitelisted relations:
          - public.resumes (a VIEW)
          - public.candidate_scores
          - public.jobdescription
          - public.email_audit
        Constraints:
          - SELECT-only (no INSERT/UPDATE/DELETE; no DDL).
          - No semicolons in the SQL.
          - Prefer COUNT(*) for 'how many' / totals.
          - Use LOWER(...) LIKE '%...%' for fuzzy text matches.
          - Prefer ordering by final_rank, final_score, created_at, sent_at when sensible.
          - Limit large result sets to 100 rows.
          - Use the actual column names you have (resumes includes candidate_* fields).
        Return ONLY the SQL text, nothing else.
        """
        sys_prompt = (
            "You are a Postgres SQL writer. Return ONLY one SELECT statement. Do not include any commentary."
        )
        schema_hint = """
    Tables/Views you may use:

    - public.resumes (VIEW): columns may include
        id, candidate_id, full_name, candidate_name, email, candidate_email,
        category, role_category, job_category, current_role, technical_skills,
        work_experience, projects, certifications, education,
        candidate_exam_url, candidate_temp_password, candidate_temp_name,
        candidate_exam_date, candidate_expiry
    - public.candidate_scores: job_id, candidate_name, final_score, final_rank,
        detailed_reasoning, strengths, weaknesses, recommendation, created_at, resume_email
    - public.jobdescription: id, job_description, role_category, categorization_confidence,
        categorization_reasoning, key_indicators, total_candidates_evaluated, created_at
    - public.email_audit: id, sent_at, job_id, candidate_name, candidate_email,
        email_type, subject, username, password, exam_link, send_status, raw_result

    Rules:
    - SELECT-only. No mutations or DDL. No semicolons.
    - If the user asks for a count, produce SELECT COUNT(*) AS cnt ...
    - If the user asks to list, include reasonable columns and LIMIT 100.
    - For role/skill filters, use LOWER(...) LIKE patterns on relevant text columns.
    - For 'latest', order by created_at or sent_at DESC.
    - For ranked candidates, join candidate_scores to resumes by LOWER(name) = LOWER(full_name) or candidate_name.
    - Always schema-qualify with public.<name>.
    """
        user_prompt = f"""User question:
    {text}

    Write ONE safe SELECT that best answers it, following the rules."""
        out = await self.llm.ainvoke(sys_prompt + "\n" + schema_hint + "\n" + user_prompt)
        sql = (out.content or "").strip()

        # Guardrails: ensure SELECT-only & no semicolons
        if not sql.lower().startswith("select"):
            raise ValueError("LLM did not return a SELECT.")
        if ";" in sql:
            sql = sql.replace(";", "")
        return sql

    
    async def handle_db_query(self, text: str) -> str:
        try:
            sql = await self._db_sql_with_llm(text)
        except Exception as e:
            return f"Couldn't derive a safe SQL for that question: {e}"
    
        r = await self.db.sql(sql)
        if r.get("status") != "success":
            return f"DB error: {r.get('error') or r}"
    
        data = r.get("data", [])
        if not data:
            return "No matching records found."
    
        # If it's a COUNT(*) result, show the number directly
        if len(data) == 1 and len(data[0].keys()) == 1:
            (only_key,) = list(data[0].keys())
            if only_key.lower() in {"cnt", "count", "count_1"}:
                return str(data[0][only_key])
    
        # Otherwise print a compact table (first 5 rows max)
        keys = list(data[0].keys())
        sample = data[: min(5, len(data))]
        head = " | ".join(keys)
        rows = [" | ".join(str(row.get(k, "")) for k in keys) for row in sample]
        out = head + "\n" + "\n".join(rows)
        if len(data) > len(sample):
            out += f"\n... (+{len(data)-len(sample)} more)"
        return out


    # ---------------- Email ----------------
    def _parse_email_action(self, text: str) -> Dict[str, Any]:
        tl = text.lower()
        # kind: invite (congrats) vs reject
        kind = "invite" if any(k in tl for k in ["congrats", "congratulation", "congratulations", "invite", "invitation"]) else "reject"
        # top N / all
        m_top = re.search(r"\btop\s+(\d+)\b", tl)
        top_n = int(m_top.group(1)) if m_top else None
        send_all = "all" in tl or "everyone" in tl
        # explicit names (for rejection like: send rejection to Jane Doe, John Smith)
        names = []
        if kind == "reject":
            m = re.search(r"to\s+(.+)$", text, flags=re.IGNORECASE)
            if m:
                raw = m.group(1)
                # split by comma or 'and'
                parts = re.split(r",| and ", raw)
                names = [p.strip() for p in parts if p.strip()]
        # explicit job id
        m_job = re.search(r"\bjob\s*id\s*(\d+)\b", tl)
        job_id = int(m_job.group(1)) if m_job else None
        return {"kind": kind, "top_n": top_n, "send_all": send_all, "names": names, "job_id": job_id}

    async def _lookup_emails_for_names(self, names: List[str]) -> List[Dict[str, Any]]:
        if not names:
            return []
        lowered = [n.lower().replace("'", "''") for n in names]
        in_list = ",".join(f"'{v}'" for v in lowered)
        # Try candidate_name first; fall back to full_name
        sql = f"""
        SELECT candidate_id, candidate_name, candidate_email
        FROM public.resumes
        WHERE candidate_email IS NOT NULL
          AND (LOWER(candidate_name) IN ({in_list}) OR LOWER(full_name) IN ({in_list}))
        """
        r = await self.db.sql(sql)
        if r.get("status") != "success":
            return []
        return r.get("data", [])

    async def _audit_email(self, job_id: Optional[int], name: str, email: str,
                           email_type: str, subject: str, username: Optional[str],
                           password: Optional[str], link: Optional[str], status: str, raw: Dict[str, Any]):
        def q(s: Optional[str]) -> str:
            if s is None:
                return "NULL"
            return "'" + s.replace("'", "''") + "'"
        jid = "NULL" if job_id is None else str(int(job_id))
        sql = f"""
        INSERT INTO public.email_audit
        (job_id, candidate_name, candidate_email, email_type, subject, username, password, exam_link, send_status, raw_result)
        VALUES ({jid}, {q(name)}, {q(email)}, {q(email_type)}, {q(subject)}, {q(username)}, {q(password)}, {q(link)}, {q(status)}, {q(json.dumps(raw, default=str))})
        """
        await self.db.sql(sql)

    async def handle_email(self, text: str) -> str:
        """
        LLM-driven email handler.
        - Uses _plan_with_llm(text) to decide action + recipients.
        - Invitations pull credentials later inside EmailOrchestrator from public.resumes.
        - Rejections are sent here and audited via MCP.
        """
        # 1) Get plan from LLM
        plan = getattr(self, "_last_plan", None)
        if not plan:
            plan = await self._plan_with_llm(text)

        rs = plan.get("recipient_spec") or {}
        action = (plan.get("action_kind") or "invite").lower()
        if action == "unknown":
            # Default to invitation when the user simply says "send the emails"
            action = "invite"

        # 2) Resolve job_id (plan → memory → DB latest)
        job_id = plan.get("job_id") or self.mem.last_job_id or await self._latest_job_id_via_mcp()
        if not job_id:
            return "I couldn't find a processed job to email. Please rank a job first, or tell me the job id."

        # 3) Build recipient map {name: email}
        recipients: dict[str, str] = {}

        # Helper to form a safe IN (...) list with proper escaping
        def _make_in_list(vals: list[str]) -> str:
            vals = [v.strip().lower().replace("'", "''") for v in vals if v and v.strip()]
            return ",".join(f"'{v}'" for v in vals) or "''"

        explicit_names = [str(n).strip() for n in (rs.get("names") or []) if str(n).strip()]
        if explicit_names:
            in_list = _make_in_list(explicit_names)
            # Try both candidate_name and full_name; prefer candidate_email then email
            sql = f"""
                SELECT
                  COALESCE(r.candidate_name, r.full_name) AS name,
                  COALESCE(r.candidate_email, r.email)     AS email
                FROM public.resumes r
                WHERE COALESCE(r.candidate_email, r.email) IS NOT NULL
                  AND (LOWER(r.full_name) IN ({in_list}) OR LOWER(r.candidate_name) IN ({in_list}))
            """
            r = await self.db.sql(sql)
            if r.get("status") != "success" or not r.get("data"):
                return "I couldn't find emails for those names."
            for row in r["data"]:
                name = (row.get("name") or "").strip()
                email = (row.get("email") or "").strip()
                if name and email:
                    recipients[name] = email

        elif rs.get("send_all", False):
            sql = f"""
                SELECT
                  cs.candidate_name AS name,
                  COALESCE(r.candidate_email, r.email, cs.resume_email, '') AS email
                FROM public.candidate_scores cs
                LEFT JOIN public.resumes r
                  ON LOWER(r.full_name) = LOWER(cs.candidate_name)
                  OR LOWER(r.candidate_name) = LOWER(cs.candidate_name)
                WHERE cs.job_id = {int(job_id)}
                ORDER BY cs.final_rank NULLS LAST, cs.final_score DESC NULLS LAST
            """
            r = await self.db.sql(sql)
            if r.get("status") != "success" or not r.get("data"):
                return "No ranked candidates found."
            for row in r["data"]:
                name = (row.get("name") or "").strip()
                email = (row.get("email") or "").strip()
                if name and email:
                    recipients[name] = email

        else:
            # top_n flow (fallback to last_top_n or 5)
            top_n = rs.get("top_n")
            if not isinstance(top_n, int) or top_n <= 0:
                top_n = self.mem.last_top_n or 5
            sql = f"""
                SELECT
                  cs.candidate_name AS name,
                  COALESCE(r.candidate_email, r.email, cs.resume_email, '') AS email
                FROM public.candidate_scores cs
                LEFT JOIN public.resumes r
                  ON LOWER(r.full_name) = LOWER(cs.candidate_name)
                  OR LOWER(r.candidate_name) = LOWER(cs.candidate_name)
                WHERE cs.job_id = {int(job_id)}
                ORDER BY cs.final_rank ASC NULLS LAST, cs.final_score DESC NULLS LAST
                LIMIT {int(top_n)}
            """
            r = await self.db.sql(sql)
            if r.get("status") != "success" or not r.get("data"):
                return "No ranked candidates found."
            for row in r["data"]:
                name = (row.get("name") or "").strip()
                email = (row.get("email") or "").strip()
                if name and email:
                    recipients[name] = email

        if not recipients:
            return "I couldn't resolve any recipients to email."

        # 4) Execute action
        if action in {"invite", "congratulations"}:
            # Send Interview Invitation - JMAN using the resume view's candidate_* fields
            res = await self.mailer.send_interview_invites(
                job_id=job_id,
                explicit_recipients=recipients  # orchestrator will pull candidate_exam_url/temp_password/... from view
            )
            self.mem.last_sent = [
                {"name": n, "email": e, "subject": "Interview Invitation - JMAN", "type": "invite"}
                for n, e in recipients.items()
            ]
            return f"Email action completed. Messages sent: {res.get('sent', 0)}."

        if action == "rejection":
            # Compose once
            subject = "Application Update"
            body_html = (
                "<p>Dear Candidate,</p>"
                "<p>Thank you for your interest. After careful consideration, we will not be moving forward at this time.</p>"
                "<p>We appreciate the time you invested and wish you the best in your future endeavors.</p>"
                "<p>Regards,<br/>JMAN Group</p>"
            )

            sent = 0
            details = []
            for name, email in recipients.items():
                result = self.mailer.gmail.send_email(to=email, subject=subject, html=body_html)
                status = "SENT" if (isinstance(result, dict) and result.get("ok", True)) else "ERROR"
                # audit via MCP (no direct DB driver)
                raw_json = json.dumps(result, default=str).replace("'", "''")
                name_q = name.replace("'", "''")
                email_q = email.replace("'", "''")
                await self.db.sql(f"""
                    INSERT INTO public.email_audit
                      (job_id, candidate_name, candidate_email, email_type, subject, send_status, raw_result)
                    VALUES
                      ({int(job_id)}, '{name_q}', '{email_q}', 'rejection', '{subject}', '{status}', '{raw_json}')
                """)
                sent += 1
                details.append({"name": name, "email": email, "type": "rejection", "subject": subject})

            self.mem.last_sent = details
            return f"Email action completed. Messages sent: {sent}."

        # Unknown action type
        return "I understood this as an email request, but couldn't determine the specific type to send."



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
        r = await self.db.sql("SELECT COUNT(*) AS cnt FROM public.email_audit")
        total = (r.get("data", [{}])[0].get("cnt", 0) if r.get("status") == "success" else 0)
        r2 = await self.db.sql("""
            SELECT sent_at, candidate_name, candidate_email, email_type, subject, username, password, exam_link, send_status
            FROM public.email_audit
            ORDER BY sent_at DESC NULLS LAST, id DESC
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
